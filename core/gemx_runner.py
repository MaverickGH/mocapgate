"""Portable GEM-X worker. Export SOMA FK, not SMPL-compatible pose guesses.

Memory: frames are decoded lazily (never the whole video in RAM), image models run in
bounded batches, and long tracks can be split into overlapping windows (--chunk-seconds /
--auto-chunk) that are stitched back with a crossfade. Resource use is reported as
`INFO [MoCapGate] memory|peak|chunk: k=v …` lines and under payload["resources"].

The helpers between the "pure helpers" markers use only the standard library (and
core.rotations), so they can be unit-tested without torch or numpy.
"""
import argparse
import gc
import importlib.util
import json
import logging
import math
import os
from pathlib import Path
import sys
import threading
import time

# Windows' Python flags are not automatically inherited by the WSL worker.
# Installed resources must stay clean even when this script is launched directly.
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


# ---------------------------------------------------------------- pure helpers (stdlib only)

# Auto-chunk heuristic (documented, conservative; calibrate with --benchmark):
#   fixed cost of the loaded image models (YOLOX, ViTPose, SAM-3D-Body ONNX backbone +
#   PyTorch decoder, CUDA context, ONNX Runtime arenas) and of the Python process, plus a
#   per-second-of-video cost for the sequence held at once (features, denoiser activations,
#   SOMA FK). Window = headroom / per-second cost, clamped to 10…120 s; off when it would
#   exceed 10 minutes. VRAM and RAM are both checked; the smaller window wins.
MODEL_VRAM_MB=4000
MODEL_RAM_MB=6000
VRAM_MB_PER_SECOND=100.0   # at 30 FPS; scales with FPS
RAM_MB_PER_SECOND=100.0
CHUNK_MIN_SECONDS,CHUNK_MAX_SECONDS,CHUNK_OFF_SECONDS=10,120,600


def auto_chunk_seconds(free_vram_mb,ram_available_mb,fps=30.0):
    """(chunk seconds, reason) from free VRAM / available RAM at start. 0 = no chunking."""
    scale=max(float(fps or 30.0),1.0)/30.0
    limits=[]
    if free_vram_mb is not None:
        limits.append(('vram',(float(free_vram_mb)-MODEL_VRAM_MB)/(VRAM_MB_PER_SECOND*scale)))
    if ram_available_mb is not None:
        limits.append(('ram',(float(ram_available_mb)-MODEL_RAM_MB)/(RAM_MB_PER_SECOND*scale)))
    if not limits:
        return 60,'unknown_memory'
    kind,raw=min(limits,key=lambda item:item[1])
    if raw>=CHUNK_OFF_SECONDS:
        return 0,'enough_memory'
    if raw<CHUNK_MIN_SECONDS:
        return CHUNK_MIN_SECONDS,'low_'+kind
    return int(min(CHUNK_MAX_SECONDS,max(CHUNK_MIN_SECONDS,raw//5*5))),'limited_by_'+kind


def plan_windows(first,last,fps,chunk_seconds,overlap_seconds=1.0):
    """Inclusive frame windows [(a, b)] covering first..last.

    Every window is chunk_seconds long (in frames at fps), neighbours overlap by at least
    overlap_seconds (at most half a window), windows are spread evenly so the last one is
    not a short remainder. chunk_seconds <= 0 or a short track → one window."""
    first,last=int(first),int(last)
    span=last-first+1
    if chunk_seconds is None or chunk_seconds<=0 or span<=0:
        return [(first,last)]
    length=max(2,int(round(float(chunk_seconds)*float(fps))))
    if span<=length:
        return [(first,last)]
    overlap=max(1,min(int(round(float(overlap_seconds)*float(fps))),length//2))
    count=math.ceil((span-overlap)/(length-overlap))
    step=(span-length)/(count-1)
    return [(first+int(round(k*step)),first+int(round(k*step))+length-1) for k in range(count)]


def crossfade_weight(k,n):
    """Weight of the incoming window at overlap frame k of n (smoothstep, strictly 0…1)."""
    t=(k+1)/(n+1)
    return t*t*(3-2*t)


def stitch(windows,frame,blend):
    """Sequential crossfade of overlapping windows → list of frames for windows[0][0]..windows[-1][1].

    frame(k, f) returns window k's value at absolute frame f; blend(x, y, w) mixes the
    stitched value x with the incoming y (w = weight of y)."""
    if not windows:
        return []
    a0,end=windows[0]
    out=[frame(0,f) for f in range(a0,end+1)]
    for k in range(1,len(windows)):
        a,b=windows[k]
        if a>end+1 or b<=end:
            raise ValueError(f'windows must overlap or touch and advance: {windows[k-1]} → {windows[k]}')
        n=end-a+1
        for i,f in enumerate(range(a,end+1)):
            out[f-a0]=blend(out[f-a0],frame(k,f),crossfade_weight(i,n))
        out.extend(frame(k,f) for f in range(end+1,b+1))
        end=b
    return out


def blend_transform(A,B,w):
    """Blend two 4×4 joint transforms: slerp of rotations, lerp of positions and per-axis scale."""
    from core.rotations import matrix_to_quat,quat_to_matrix,slerp
    def split(M):
        scale=[math.sqrt(sum(M[r][c]**2 for r in range(3))) or 1.0 for c in range(3)]
        R=[[M[r][c]/scale[c] for c in range(3)] for r in range(3)]
        return R,scale,[M[r][3] for r in range(3)]
    Ra,sa,pa=split(A);Rb,sb,pb=split(B)
    R=quat_to_matrix(slerp(matrix_to_quat(Ra),matrix_to_quat(Rb),w))
    s=[x+(y-x)*w for x,y in zip(sa,sb)];p=[x+(y-x)*w for x,y in zip(pa,pb)]
    return [[R[r][0]*s[0],R[r][1]*s[1],R[r][2]*s[2],p[r]] for r in range(3)]+[[0.0,0.0,0.0,1.0]]


def mean_offset(reference,moving):
    """Mean of reference − moving over paired 3D points (aligns a window to its predecessor)."""
    pairs=list(zip(reference,moving))
    if not pairs:
        return [0.0,0.0,0.0]
    return [sum(r[i]-m[i] for r,m in pairs)/len(pairs) for i in range(3)]


# GEM-X static_conf_logits (upstream gem/pipeline/postprocess.py, SOMA77_CONTACT_JOINT_IDS):
# [L_ankle, L_foot(toe), R_ankle, R_foot(toe), L_wrist, R_wrist]; foot contact = max(ankle, toe).
CONTACT_COLUMNS={'Left':(0,1),'Right':(2,3)}


def foot_contacts(windows,rows,total,first,last):
    """Per-window per-frame contact probabilities → {'Left': [p]*total, 'Right': [...]}.

    windows — [(a, b)] inclusive absolute frames, rows[k] — window k's frames of ≥4 probabilities
    (CONTACT_COLUMNS). Overlaps are crossfaded like the motion; 0.0 outside first..last.
    None when any window has no contact output (older model/ONNX without the head)."""
    if not windows or any(r is None or not len(r) for r in rows):
        return None
    def frame(k,f):
        r=rows[k];return r[min(len(r)-1,max(0,f-windows[k][0]))]
    seq=stitch(windows,frame,lambda x,y,w:[p+(q-p)*w for p,q in zip(x,y)])
    a0=windows[0][0];out={}
    for side,cols in CONTACT_COLUMNS.items():
        out[side]=[round(max(float(seq[f-a0][c]) for c in cols),3) if first<=f<=last and 0<=f-a0<len(seq) else 0.0
                   for f in range(int(total))]
    return out


def shorten_state_dict_message(message):
    """Huge 'state dict do not match' warnings → one line with key counts; other text unchanged."""
    text=str(message)
    if 'do not match exactly' not in text and not text.startswith(('Missing keys:','Unexpected keys:')):
        return text
    def count(label):
        for line in text.splitlines():
            if label in line:
                rest=line.split(':',1)[1].strip().strip('[]')
                return len([k for k in rest.split(',') if k.strip()])
        return 0
    if 'do not match exactly' in text:
        return (f'Checkpoint loaded non-strictly: {count("missing keys")} missing, '
                f'{count("unexpected key")} unexpected keys (expected for the hybrid ONNX backbone; details hidden)')
    label='Missing keys' if text.startswith('Missing') else 'Unexpected keys'
    return f'{label}: {count(label)} (details hidden)'


def format_line(kind,values):
    """`INFO [MoCapGate] <kind>: k=v …` (None → None, floats rounded)."""
    def show(v):
        if v is None:return 'None'
        if isinstance(v,float):return f'{v:.1f}' if abs(v)<1e6 else str(int(v))
        return str(v).replace(' ','_')
    return f'INFO [MoCapGate] {kind}: '+' '.join(f'{k}={show(v)}' for k,v in values.items())


# ---------------------------------------------------------------- end of pure helpers


class _ShortStateDict(logging.Filter):
    def filter(self,record):
        try:
            message=record.getMessage()
        except Exception:  # noqa: BLE001
            return True
        short=shorten_state_dict_message(message)
        if short!=message:
            record.msg,record.args=short,()
        return True


def quiet_state_dict_warnings():
    """Shorten SAM-3D-Body / GEM checkpoint key dumps (harmless, but thousands of names)."""
    for name in ('sam_3d_body.utils.checkpoint','gem',''):
        logging.getLogger(name).addFilter(_ShortStateDict())
    import warnings
    warnings.filterwarnings('ignore',message='.*do not match exactly.*')


class ResourceMonitor:
    """Samples VRAM (device-wide, includes ONNX Runtime), system RAM (inside WSL: the VM) and
    this process's peak RSS every half second; prints stage and peak lines."""

    def __init__(self,torch):
        from core import resources
        self.resources,self.torch=resources,torch
        self.cuda=bool(torch is not None and torch.cuda.is_available())
        self.start=time.monotonic();self.stage_start=self.start;self.stage_name=None
        self.stages={};self.peak={'vram_mb':None,'ram_mb':None}
        self.totals={'vram_total_mb':None,'ram_total_mb':None}
        self.gpu=torch.cuda.get_device_name(0) if self.cuda else None
        self.lock=threading.Lock();self.stop=threading.Event()
        self.thread=threading.Thread(target=self._loop,daemon=True)
        self.thread.start()

    def vram(self):
        if not self.cuda:return None,None
        try:
            free,total=self.torch.cuda.mem_get_info(0)
            return (total-free)//2**20,total//2**20
        except Exception:  # noqa: BLE001
            return None,None

    def rss_mb(self):
        try:
            import resource
            peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            return int(peak/2**20) if sys.platform=='darwin' else int(peak/1024)
        except Exception:  # noqa: BLE001
            return None

    def sample(self):
        used,total=self.vram();ram=self.resources.memory() or {}
        with self.lock:
            if used is not None:
                self.peak['vram_mb']=max(self.peak['vram_mb'] or 0,used);self.totals['vram_total_mb']=total
            if ram.get('used_mb') is not None:
                self.peak['ram_mb']=max(self.peak['ram_mb'] or 0,ram['used_mb']);self.totals['ram_total_mb']=ram['total_mb']
        return used,total,ram

    def _loop(self):
        # macOS samples via sysctl/vm_stat subprocesses — less often
        while not self.stop.wait(2.0 if sys.platform=='darwin' else 0.5):
            self.sample()

    def stage(self,name):
        """Close the previous stage (its duration) and print current memory."""
        now=time.monotonic()
        if self.stage_name:
            self.stages[self.stage_name]=round(self.stages.get(self.stage_name,0.0)+now-self.stage_start,3)
        self.stage_name,self.stage_start=name,now
        used,total,ram=self.sample()
        print(format_line('memory',{'vram_used_mb':used,'vram_total_mb':total,'ram_used_mb':ram.get('used_mb'),
                                    'ram_total_mb':ram.get('total_mb'),'rss_mb':self.rss_mb(),'stage':name}),flush=True)

    def finish(self):
        self.stage('done');self.stop.set()
        seconds=round(time.monotonic()-self.start,3)
        with self.lock:
            peaks={'vram_mb':self.peak['vram_mb'],'ram_mb':self.peak['ram_mb'],'rss_mb':self.rss_mb(),'seconds':seconds,
                   **self.totals,'gpu':self.gpu}
        print(format_line('peak',{k:peaks[k] for k in ('vram_mb','ram_mb','rss_mb','seconds','vram_total_mb','ram_total_mb')}),flush=True)
        return {**peaks,'stages':dict(self.stages)}


def watch_contacts(demo):
    """Перехват выходов GEM-X для контактов стоп → dict, который заполняется при каждом run_inference_fast.

    'static_conf_logits' — из ONNX-денойзера (upstream run_denoiser_onnx берёт только pred_x/pred_cam,
    хотя OnnxRunner возвращает все выходы модели); 'model' — экземпляр GEM, созданный внутри
    run_inference_fast (его EnDecoder нужен постобработке контактов)."""
    import hydra
    seen={}
    denoise=demo.run_denoiser_onnx
    def denoise_spy(runner,backend,batch):
        def spy(**kw):
            out=runner(**kw)
            if hasattr(out,'get') and out.get('static_conf_logits') is not None:seen['static_conf_logits']=out['static_conf_logits']
            return out
        return denoise(spy,backend,batch)
    demo.run_denoiser_onnx=denoise_spy
    instantiate=hydra.utils.instantiate
    def keep_model(*a,**kw):
        made=instantiate(*a,**kw)
        if hasattr(made,'endecoder'):seen['model']=made
        return made
    hydra.utils.instantiate=keep_model
    return seen


def static_conf_rows(pred,torch):
    """Вероятности контакта (sigmoid static_conf_logits) по кадрам: [[L_ankle, L_toe, R_ankle, R_toe], ...] или None."""
    logits=pred.get('static_conf_logits')
    if logits is None:logits=(pred.get('net_outputs') or {}).get('static_conf_logits')
    if logits is None or logits.shape[-1]<4:return None
    return [[round(v,4) for v in row] for row in torch.sigmoid(logits.detach().float().cpu().reshape(-1,logits.shape[-1])[:,:4]).tolist()]


def contact_postprocess(pred,logits,endecoder,torch):
    """Постобработка контактов upstream (gem_pipeline.py: refine_translation_with_contacts +
    refine_pose_with_contact_ik) для быстрого режима: в upstream ONNX-демо её нет."""
    from gem.pipeline.postprocess import refine_pose_with_contact_ik,refine_translation_with_contacts
    glob=pred['body_params_global']
    if logits.shape[-2]!=glob['transl'].shape[0]:
        raise ValueError('static_conf_logits length mismatch')
    device=torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    params={k:v[None].to(device).float() for k,v in glob.items()}
    outputs={'static_conf_logits':logits.reshape(1,-1,logits.shape[-1]).to(device).float(),'pred_body_params_global':params}
    with torch.no_grad():
        params['transl']=refine_translation_with_contacts(outputs,endecoder)
        body_pose=refine_pose_with_contact_ik(outputs,endecoder)
    glob['transl']=params['transl'][0].cpu()
    glob['body_pose']=body_pose[0].cpu()
    pred['body_params_incam']['body_pose']=body_pose[0].cpu()


def free_memory(torch):
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def preprocess_people(demo,jobs,loaded,torch):
    """Keep ViTPose and SAM image models in separate GPU phases, including resumes.

    A completed first window can already have ViTPose cached on disk. Loading SAM
    for it before ViTPose is needed by the next window fills small GPUs. Prepare
    all keypoints first and release that model before starting body features.
    """
    for image_features in (False,True):
        for index,_,windows in jobs:
            label=f' {index}/{len(jobs)}' if len(jobs)>1 else ''
            for number,(_,_,window) in enumerate(windows,1):
                if Path(window.paths.hpe_results).is_file():
                    continue
                part=f' (фрагмент {number}/{len(windows)})' if len(windows)>1 else ''
                step='Признаки тела (SAM-3D-Body)' if image_features else '2D-точки тела'
                print(f'STAGE Участник{label}: {step}{part}',flush=True)
                demo.run_preprocess_fast(window,no_imgfeat=not image_features)
                free_memory(torch)
        loaded.clear()
        free_memory(torch)


class VideoFrames:
    """Lazy RGB frames of a video range: len(), shape, int/slice indexing, iteration.

    Decodes forward with PyAV and keeps only the current frame, so callers that walk the
    video in order (YOLOX, ViTPose, SAM-3D-Body batches) never hold the whole clip in RAM.
    A slice materialises just that batch. Going backwards reopens the file (seek to the
    nearest keyframe). Missing trailing frames repeat the last decoded one."""

    def __init__(self,path,start=0,count=None,scale=1.0,size=None):
        import av
        self.av,self.path,self.start,self.scale=av,str(path),int(start),float(scale)
        self.count=count;self._gen=None;self._pos=None;self._last=None
        width,height=size or (None,None)
        if width is None:
            with av.open(self.path) as container:
                ctx=container.streams.video[0].codec_context;width,height=ctx.width,ctx.height
        self.size=(int(round(width*self.scale)),int(round(height*self.scale)))

    @property
    def shape(self):
        return (len(self),self.size[1],self.size[0],3)

    def __len__(self):
        return int(self.count)

    def _decode(self,first):
        """(absolute index, RGB array) from frame `first` on; seeks when the index is known
        from timestamps (constant-FPS video), otherwise counts frames from the start."""
        if first>0:
            with self.av.open(self.path) as container:
                stream=container.streams.video[0];stream.thread_type='AUTO'
                rate=float(stream.average_rate or stream.guessed_rate or 0);base=float(stream.time_base or 0)
                origin=stream.start_time or 0
                usable=rate>0 and base>0
                if usable:
                    container.seek(int(origin+max(0.0,(first-1)/rate)/base),stream=stream,backward=True,any_frame=False)
                    started=False
                    for frame in container.decode(stream):
                        if frame.pts is None:
                            usable=False;break
                        index=int(round((frame.pts-origin)*base*rate))
                        if not started and index>first:
                            usable=False;break  # keyframe seek overshot
                        started=True
                        if index<first:continue
                        yield index,self._image(frame)
                    if usable:return
        with self.av.open(self.path) as container:
            stream=container.streams.video[0];stream.thread_type='AUTO'
            for index,frame in enumerate(container.decode(stream)):
                if index>=first:
                    yield index,self._image(frame)

    def _image(self,frame):
        if self.scale!=1.0:
            frame=frame.reformat(width=self.size[0],height=self.size[1])
        return frame.to_ndarray(format='rgb24')

    def frame(self,i):
        if i<0:i+=len(self)
        if not 0<=i<len(self):raise IndexError(i)
        target=self.start+i
        if self._last is not None and (self._last[0]==target or (self._gen is None and target>=self._pos)):
            return self._last[1]  # same frame again, or past the decoded end: repeat the last one
        if self._gen is None or self._pos is None or target<self._pos:
            self._gen=self._decode(target);self._pos=target;self._last=None
        for index,image in self._gen:
            self._pos=index+1;self._last=(index,image)
            if index>=target:return image
        self._gen=None  # end of file before `count` frames
        if self._last is None:raise IndexError(i)
        return self._last[1]

    def __getitem__(self,key):
        import numpy as np
        if isinstance(key,slice):
            start,stop,step=key.indices(len(self))
            if step!=1:return np.stack([self.frame(i) for i in range(start,stop,step)])
            if stop<=start:return np.zeros((0,self.size[1],self.size[0],3),dtype=np.uint8)
            return np.stack([self.frame(i) for i in range(start,stop)])
        return self.frame(int(key))

    def __iter__(self):
        for i in range(len(self)):
            yield self.frame(i)


def warp_cpu_fallback(soma_layer_cls, log=print):
    """Warp без видеокарты (сборка под CUDA 13 на драйвере CUDA 12, сломанный libcuda в WSL), а PyTorch — на CUDA:
    SOMA передала бы Warp устройство cuda:0, которого у него нет (IndexError в device_from_torch).
    Тогда скиннинг SOMA — в режиме PyTorch, а подбор поворотов на Warp — на процессоре с возвратом на GPU.
    Возвращает True, если запасной путь включён."""
    try:
        import torch
        if not torch.cuda.is_available():
            return False
        import warp as wp
        try:
            wp.init()
            cuda_devices = wp.get_cuda_device_count()
        except Exception:  # noqa: BLE001 — любой сбой Warp = видеокарты в Warp нет
            cuda_devices = 0
        if cuda_devices:
            return False
    except ImportError:
        return False
    log('INFO [MoCapGate] warp: no CUDA device in Warp (driver/toolkit mismatch) — SOMA uses PyTorch skinning and '
        'CPU rotation fitting. Update the NVIDIA driver to 580+ or reinstall GEM-X for full speed.', flush=True)
    original_init = soma_layer_cls.__init__

    def init(self, *args, **kwargs):
        kwargs['mode'] = 'torch'  # любое значение кроме "warp" — плотный скиннинг PyTorch
        original_init(self, *args, **kwargs)
    soma_layer_cls.__init__ = init

    def on_cpu(fn):
        def wrapped(*args, **kwargs):
            device = next((a.device for a in list(args) + list(kwargs.values()) if torch.is_tensor(a)), None)
            move = lambda v: v.detach().cpu() if torch.is_tensor(v) else v
            result = fn(*[move(a) for a in args], **{k: move(v) for k, v in kwargs.items()})
            back = lambda v: v.to(device) if torch.is_tensor(v) and device is not None else v
            return tuple(back(r) for r in result) if isinstance(result, tuple) else back(result)
        return wrapped
    # все места SOMA, где Warp вызывается напрямую (не через режим слоя), — на процессор
    for module, names in (('soma.geometry.skeleton_transfer', ('align_vectors_warp', 'parallel_rodrigues_kabsch_warp',
                                                               'rodrigues_rotation_warp')),
                          ('soma.geometry.lbs_warp', ('linear_blend_skinning',)),
                          ('soma.pose_inversion', ('linear_blend_skinning',))):
        try:
            target = importlib.import_module(module)
        except ImportError:
            continue
        for name in names:
            if getattr(target, name, None) is not None:
                setattr(target, name, on_cpu(getattr(target, name)))
    return True


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('repo',type=Path);parser.add_argument('video',type=Path);parser.add_argument('output',type=Path)
    parser.add_argument('--max-people',type=int,choices=range(1,9),default=1)
    parser.add_argument('--fps',type=float,default=30.0,help='частота кадров входного видео (оно уже приведено к ней)')
    # раскрыть GEM-X: режим модели, камера, детектор и трекер людей
    parser.add_argument('--quality',choices=('fast','accurate','max'),default='fast',
                        help='fast — ONNX; accurate — PyTorch + постобработка контактов стоп; max — PyTorch DDIM 50 шагов')
    parser.add_argument('--f-mm',type=float,default=0.0,help='фокус, мм 35-мм экв.; 0 — оценка GEM-X')
    parser.add_argument('--score-thr',type=float,default=0.5,help='порог уверенности детектора людей YOLOX')
    parser.add_argument('--min-seconds',type=float,default=0.25,help='минимальная длительность участника')
    parser.add_argument('--max-lost',type=int,default=30,help='сколько кадров помнить потерянного человека')
    # память: батчи, фрагменты, замеры
    parser.add_argument('--batch-size',type=int,default=0,help='кадров на батч ViTPose/SAM-3D-Body; 0 — авто по VRAM')
    parser.add_argument('--chunk-seconds',type=float,default=0.0,help='длина фрагмента трека, с; 0 — без разбиения')
    parser.add_argument('--chunk-overlap',type=float,default=1.0,help='перекрытие соседних фрагментов, с')
    parser.add_argument('--auto-chunk',action='store_true',help='выбрать длину фрагмента по свободной VRAM/RAM')
    parser.add_argument('--benchmark',action='store_true',help='записать в output JSON замеров вместо сцены')
    args=parser.parse_args()
    if args.fps<=0:parser.error('--fps must be positive')
    if args.chunk_seconds<0 or args.chunk_overlap<0 or args.batch_size<0:parser.error('negative chunk/batch values')
    repo,video,output=args.repo.resolve(),args.video.resolve(),args.output.resolve()
    os.chdir(repo);sys.path.insert(0,str(repo))
    import torch
    quiet_state_dict_warnings()
    monitor=ResourceMonitor(torch)
    monitor.stage('start')
    image_batch = 2
    if sys.platform == 'linux':
        if not torch.cuda.is_available():
            raise RuntimeError('GEM-X Linux requires NVIDIA CUDA.')
        if torch.cuda.get_device_properties(0).total_memory <= 10*1024**3:
            image_batch = 1
        # The default power-of-two arena growth can spill several GB into
        # shared Windows memory on 8 GB cards, making every frame very slow.
        import onnxruntime as ort
        original_session = ort.InferenceSession
        def cuda_session(path, *a, **kw):
            providers = kw.get('providers')
            if providers:
                tuned = []
                for provider in providers:
                    name, options = provider if isinstance(provider, tuple) else (provider, {})
                    memory_options = {'arena_extend_strategy': 'kSameAsRequested'}
                    if image_batch == 1:
                        memory_options.update(cudnn_conv_use_max_workspace='0', cudnn_conv_algo_search='HEURISTIC')
                    tuned.append((name, {**options, **memory_options})
                                 if name == 'CUDAExecutionProvider' else provider)
                kw['providers'] = tuned
            return original_session(path, *a, **kw)
        ort.InferenceSession = cuda_session
    if args.batch_size:
        image_batch = args.batch_size  # read lazily by the ONNX session options above
    if sys.platform=='darwin':
        # Upstream ONNX uses CoreML; its geometry helper still calls .cuda().
        # Keep those helper tensors on CPU within this isolated worker only.
        torch.Tensor.cuda=lambda self,*a,**k:self.cpu()
        torch.nn.Module.cuda=lambda self,*a,**k:self.cpu()
        from lightning_fabric.utilities.device_dtype_mixin import _DeviceDtypeModuleMixin
        _DeviceDtypeModuleMixin.cuda=lambda self,*a,**k:self.cpu()
        tensor_to,module_to=torch.Tensor.to,torch.nn.Module.to
        def cpu_args(a,kw):
            def remap(v):
                return 'cpu' if isinstance(v,(str,torch.device)) and str(v).startswith('cuda') else v
            return tuple(remap(v) for v in a),{k:remap(v) if k=='device' else v for k,v in kw.items()}
        def tensor_cpu(self,*a,**kw):
            a,kw=cpu_args(a,kw);return tensor_to(self,*a,**kw)
        def module_cpu(self,*a,**kw):
            a,kw=cpu_args(a,kw);return module_to(self,*a,**kw)
        torch.Tensor.to=tensor_cpu;torch.nn.Module.to=module_cpu
        import onnxruntime as ort
        session=ort.InferenceSession
        class MacSession:
            def __init__(self,path,*a,**kw):
                self.path,self.args,self.kw=path,a,kw
                # CoreML's NMS output-rank inference fails for this YOLOX graph.
                if any(name in str(path).lower() for name in ('yolox','vitpose','sam3db_backbone')):
                    kw={**kw,'providers':['CPUExecutionProvider']}
                self.inner=session(path,*a,**kw)
            def __getattr__(self,name):return getattr(self.inner,name)
            def run(self,*a,**kw):
                try:return self.inner.run(*a,**kw)
                except ort.capi.onnxruntime_pybind11_state.Fail as exc:
                    if 'CoreML' not in str(exc):raise
                    print('CoreML unsupported graph; retrying on CPU.',flush=True)
                    self.inner=session(self.path,*self.args,**{**self.kw,'providers':['CPUExecutionProvider']})
                    return self.inner.run(*a,**kw)
        ort.InferenceSession=MacSession
    spec=importlib.util.spec_from_file_location('gem_demo',repo/'scripts/demo/demo_soma_onnx.py')
    demo=importlib.util.module_from_spec(spec);spec.loader.exec_module(demo)
    quiet_state_dict_warnings()  # upstream imports may have configured their loggers
    # Inference needs no OpenGL/PyTorch3D renderer. Avoid upstream's optional
    # renderer imports on headless computers and Apple Silicon.
    from gem.utils.kp2d_utils import smooth_bbx_xyxy
    from gem.utils.net_utils import detach_to_cpu, to_cuda
    from gem.utils.soma_utils.soma_layer import SomaLayer
    warp_cpu_fallback(SomaLayer)  # драйвер не тянет Warp на GPU — не падать, а считать подгонку на процессоре
    from gem.utils import video_io_utils
    from gem.utils.video_io_utils import get_video_lwh, read_video_np
    demo.smooth_bbx_xyxy=smooth_bbx_xyxy
    demo.detach_to_cpu=detach_to_cpu;demo.to_cuda=to_cuda
    demo.SomaLayer=SomaLayer
    # Lazy frames instead of whole-video arrays (a 549-frame 4K clip is ~13 GB decoded,
    # and upstream decodes it again for detection, ViTPose and SAM-3D-Body). Window paths
    # "<video>#mocapgate=a-b" read only frames a..b of the real file.
    virtual={};lwh_cache={}
    def resolve(path):
        return virtual.get(str(path),(str(path),0,None))
    def lazy_lwh(path):
        real,first,count=resolve(path)
        if real not in lwh_cache:lwh_cache[real]=get_video_lwh(real)
        length,width,height=lwh_cache[real]
        return (count if count is not None else length),width,height
    try:
        import av  # noqa: F401 — PyAV backs imageio's pyav plugin in the GEM-X environment
        def lazy_read(path,start_frame=0,end_frame=-1,scale=1.0):
            real,first,_=resolve(path)
            length,width,height=lazy_lwh(path)
            stop=length if end_frame is None or end_frame<0 else min(end_frame,length)
            return VideoFrames(real,first+start_frame,max(0,stop-start_frame),scale,(width,height))
    except ImportError:
        print('PyAV unavailable: decoding whole videos into RAM.',flush=True)
        def lazy_read(path,start_frame=0,end_frame=-1,scale=1.0):
            real,first,count=resolve(path)
            if count is None:return read_video_np(real,start_frame,end_frame,scale)
            stop=first+count if end_frame is None or end_frame<0 else first+end_frame
            return read_video_np(real,first+start_frame,stop,scale)
    demo.get_video_lwh=lazy_lwh;demo.read_video_np=lazy_read
    video_io_utils.read_video_np=lazy_read
    demo._ensure_pipeline_deps=lambda:None
    if sys.platform=='darwin':
        import gem.utils.yolox_detector as detector
        from gem.utils import sam3db_extractor
        original_extractor=sam3db_extractor.SAM3DBExtractor
        sam3db_extractor.SAM3DBExtractor=lambda *a,**kw:original_extractor(*a,**{**kw,'device':'cpu'})
        original_detector=detector.YOLOXDetector
        detector.YOLOXDetector=lambda *a,**kw:original_detector(*a,**{**kw,'device':'cpu'})
    # своя папка на каждый набор настроек: кэш препроцесса не переиспользуется с другими порогами/режимом
    sys.argv=['demo','--video',str(video),'--output_root',str(output.parent/'gemx'/output.stem),'--static_cam']
    parsed=demo._parse_args()
    # Hydra paths must be quoted, including spaces and Cyrillic names.
    import hydra
    compose=hydra.compose
    def safe_compose(*a,**kw):
        kw['overrides']=[k+'='+json.dumps(v,ensure_ascii=False) if k in ('video_path','video_name','output_root','ckpt_path') else item
            for item in kw.get('overrides',[]) for k,_,v in [item.partition('=')]]
        return compose(*a,**kw)
    hydra.compose=safe_compose
    try:cfg=demo._build_cfg(parsed)
    finally:hydra.compose=compose
    # Bound image-model batches rather than allocating for the full sequence.
    from gem.utils import sam3db_extractor
    sam3db_extractor.read_video_np=lazy_read
    def body_progress(iterable, *a, **kw):
        total = len(iterable)
        # Upstream's carriage-return progress bar shares the stdout/stderr
        # pipe and can corrupt JSON lines. Emit only our structured events.
        for completed, item in enumerate(iterable, 1):
            yield item
            if completed == 1 or completed % 5 == 0 or completed == total:
                print(json.dumps({'stage': 'gemx', 'message': f'SAM 3D Body: {completed}/{total}',
                                  'progress': None}), flush=True)
    sam3db_extractor.tqdm = body_progress
    original_extract=sam3db_extractor.SAM3DBExtractor.extract_video_features if isinstance(sam3db_extractor.SAM3DBExtractor,type) else original_extractor.extract_video_features
    extractor_class=sam3db_extractor.SAM3DBExtractor if isinstance(sam3db_extractor.SAM3DBExtractor,type) else original_extractor
    def extract_batch(self,*a,**kw):
        return original_extract(self,*a,**{**kw,'batch_size':1 if sys.platform=='darwin' else image_batch})
    extractor_class.extract_video_features=extract_batch
    vitpose=demo.run_vitpose_onnx
    def vitpose_blocks(runner,backend,frames,bbx_xys,batch_size=16):
        # upstream crops the whole sequence to float32 first (~0.8 MB per frame); do it per block
        if backend=='pytorch':return vitpose(runner,backend,frames,bbx_xys,batch_size=image_batch)
        block=64;parts=[]
        for start in range(0,len(frames),block):
            parts.append(vitpose(runner,backend,frames[start:start+block],bbx_xys[start:start+block],batch_size=image_batch))
        return torch.cat(parts,dim=0)
    demo.run_vitpose_onnx=vitpose_blocks
    # Image models are loaded once for all people/windows, then released before the denoiser.
    loaded={}
    load_vitpose,load_sam3db=demo.load_vitpose,demo.load_sam3db
    def cached_vitpose(*a,**kw):
        if 'vitpose' not in loaded:loaded['vitpose']=load_vitpose(*a,**kw)
        return loaded['vitpose']
    def cached_sam3db(*a,**kw):
        if 'sam3db' not in loaded:loaded['sam3db']=load_sam3db(*a,**kw)
        return loaded['sam3db']
    demo.load_vitpose,demo.load_sam3db=cached_vitpose,cached_sam3db
    if sys.platform=='darwin':
        from gem.utils.soma_utils import soma_layer
        original_soma=soma_layer.SomaLayer
        soma_layer.SomaLayer=lambda *a,**kw:original_soma(*a,**{**kw,'device':'cpu','mode':'torch'})
        demo.SomaLayer=soma_layer.SomaLayer
    from gem.utils.soma_utils.soma_layer import SomaLayer
    if args.f_mm>0:
        # фокус задан: K для препроцесса (SAM-3D-Body) и для модели — из мм 35-мм эквивалента
        def focal_K(width,height):
            K=torch.eye(3);f=args.f_mm/36.0*float(max(width,height))
            K[0,0]=K[1,1]=f;K[0,2]=float(width)/2;K[1,2]=float(height)/2
            return K
        demo.estimate_K=focal_K
    # фрагменты: вручную или по свободной памяти в начале
    chunk_seconds=args.chunk_seconds
    if args.auto_chunk:
        free_vram=None
        if torch.cuda.is_available():
            try:free_vram=torch.cuda.mem_get_info(0)[0]//2**20
            except Exception:free_vram=None  # noqa: BLE001
        from core import resources
        ram=resources.memory() or {}
        chunk_seconds,reason=auto_chunk_seconds(free_vram,ram.get('available_mb'),args.fps)
        print(format_line('chunk',{'seconds':chunk_seconds,'overlap':args.chunk_overlap,'mode':'auto','reason':reason,
                                   'free_vram_mb':free_vram,'ram_available_mb':ram.get('available_mb'),'fps':args.fps}),flush=True)
    elif chunk_seconds>0:
        print(format_line('chunk',{'seconds':chunk_seconds,'overlap':args.chunk_overlap,'mode':'manual','fps':args.fps}),flush=True)
    else:
        print(format_line('chunk',{'seconds':0,'mode':'off','fps':args.fps}),flush=True)
    monitor.stage('detect')
    # детекция и трекинг всегда наши — пороги из настроек применяются и к одному человеку
    tracks=detect_people(demo,cfg,args.max_people,args.fps,args.score_thr,args.min_seconds,args.max_lost)
    free_memory(torch)
    total,width,height=demo.get_video_lwh(cfg.video_path)
    from copy import deepcopy
    from omegaconf import open_dict
    jobs=[]  # (person index, track, [(a, b, cfg)])
    for index,(pid,person_cfg,first,last) in enumerate(tracks,1):
        end=total-1 if last is None else int(last)
        planned=plan_windows(first,end,args.fps,chunk_seconds,args.chunk_overlap) if chunk_seconds>0 else [(0,total-1)]
        if len(planned)==1:
            windows=[(0,total-1,person_cfg)]  # как раньше: всё видео, кэш участника
        else:
            boxes=torch.load(person_cfg.paths.bbx,map_location='cpu')
            windows=[]
            for a,b in planned:
                window=deepcopy(person_cfg)
                path=f'{video}#mocapgate={a}-{b}'
                virtual[path]=(str(video),a,b-a+1)
                with open_dict(window):
                    window.video_path=path
                    window.output_dir=str(Path(person_cfg.output_dir)/f'window_{a}_{b}')
                    window.preprocess_dir=str(Path(window.output_dir)/'preprocess')
                Path(window.preprocess_dir).mkdir(parents=True,exist_ok=True)
                if not Path(window.paths.bbx).is_file():
                    torch.save({key:value[a:b+1].clone() for key,value in boxes.items()},window.paths.bbx)
                windows.append((a,b,window))
            print(f'STAGE Участник {index}: {len(windows)} фрагм. по {chunk_seconds:g} с',flush=True)
        jobs.append((index,(pid,first,end),windows))
    monitor.stage('preprocess')
    preprocess_people(demo,jobs,loaded,torch)
    monitor.stage('inference')
    seen=watch_contacts(demo)
    mode={'fast':'быстро (ONNX)','accurate':'точно (PyTorch + контакты стоп)','max':'максимум (DDIM 50 шагов)'}[args.quality]
    results=[]
    for index,(pid,first,end),windows in jobs:
        label=f' {index}/{len(tracks)}' if len(tracks)>1 else ''
        preds=[]
        for number,(a,b,window) in enumerate(windows,1):
            if Path(window.paths.hpe_results).is_file():
                pred=torch.load(window.paths.hpe_results,map_location='cpu')
            else:
                part=f' (фрагмент {number}/{len(windows)})' if len(windows)>1 else ''
                print(f'STAGE Участник{label}: движение GEM-X — {mode}{part}',flush=True)
                data=demo.load_data_dict(window)
                seen.clear()
                pred=demo.run_inference_fast(window,data,force_pytorch=args.quality!='fast',use_ddim=args.quality=='max')
                if pred.get('K_fullimg') is None:pred['K_fullimg']=data['K_fullimg']
                logits=seen.pop('static_conf_logits',None);model=seen.pop('model',None);seen.clear()
                state='pytorch' if args.quality!='fast' else 'none'
                if args.quality=='fast' and logits is not None:
                    # upstream ONNX demo drops static_conf_logits and skips contact postproc; PyTorch predict applies it
                    pred['static_conf_logits']=logits.detach().cpu()
                    state='no_model'
                    if model is not None:
                        try:contact_postprocess(pred,logits,model.endecoder,torch);state='applied'
                        except Exception as error:state='failed_'+type(error).__name__  # noqa: BLE001
                print(format_line('contacts',{'quality':args.quality,'onnx_logits':logits is not None,'postproc':state}),flush=True)
                del model,logits
                torch.save(pred,window.paths.hpe_results)
                del data
            preds.append({'body_params_global':pred['body_params_global'],'body_params_incam':pred['body_params_incam'],
                          'K':pred['K_fullimg'][0].tolist() if pred.get('K_fullimg') is not None else None,
                          'contacts':static_conf_rows(pred,torch)})
            del pred;free_memory(torch)
        results.append((pid,first,end,windows,preds))
    monitor.stage('scene')
    # The CPU body model is needed only for FK, after image-model memory is freed.
    layer=SomaLayer(data_root='inputs/soma_assets',device='cpu',mode='torch').soma
    captured=[]
    for pid,first,end,windows,preds in results:
        params=[p['body_params_global'] for p in preds]
        identity=params[0] if len(params)==1 else {key:torch.cat([p[key] for p in params]) for key in ('scale_params','identity_coeffs')}
        neutral=prepare_identity(layer,identity,torch)
        globs=[pose_sequence(layer,p['body_params_global'],torch) for p in preds]
        cams=[pose_sequence(layer,p['body_params_incam'],torch) for p in preds]  # где человек был относительно камеры
        K=next((p['K'] for p in preds if p['K'] is not None),None)
        if K is None:K=demo.estimate_K(width,height).tolist()
        # исходные суставы ног: та же поза на фигуре своего кадра (модель предсказывает её по кадрам) —
        # для точного ретаргета ног на BVH с постоянными длинами костей (средняя фигура)
        legs=[i for i,n in enumerate(scene_names(layer)) if n in SOURCE_JOINTS]
        deltas=None;started=time.time()
        try:
            deltas=[source_deltas(layer,p['body_params_global'],g,legs,torch) for p,g in zip(preds,globs)]
            worst=max(float(d.norm(dim=-1).max()) for d in deltas)*100
            print(format_line('identity_check',{'joints':len(legs),'max_delta_cm':f'{worst:.2f}','seconds':round(time.time()-started,1)}),flush=True)
        except Exception as error:  # noqa: BLE001 — диагностика и ретаргет не должны ронять распознавание
            print(format_line('identity_check',{'failed':type(error).__name__}),flush=True);deltas=None
        contacts=foot_contacts([(a,b) for a,b,_ in windows],[p['contacts'] for p in preds],total,first,end)
        if len(windows)==1:
            glob,cam=globs[0],cams[0]
            source=deltas[0] if deltas else None
        elif deltas:
            glob,cam,source=stitch_windows([(a,b) for a,b,_ in windows],globs,cams,total,torch,extras=deltas)
        else:
            glob,cam=stitch_windows([(a,b) for a,b,_ in windows],globs,cams,total,torch);source=None
        captured.append({'id':int(pid),'first':int(first),'last':int(end),'neutral':neutral,'glob':glob,'cam':cam,'K':K,
                         'contacts':contacts,'source':source,'source_index':legs})
    print('STAGE Общая сцена: камера, пол, высота',flush=True)
    payload=build_scene(layer,captured,width,height,torch,fps=args.fps)
    peaks=monitor.finish()
    payload['resources']=peaks
    if args.benchmark:
        seconds=peaks['seconds'] or 0.0
        frames=int(total)
        report={'resources':{k:v for k,v in peaks.items() if k!='stages'},'seconds':peaks['stages'],'frames':frames,
                'fps_processing':round(frames/seconds,3) if seconds else None,'people':len(captured),
                'windows':sum(len(w) for _,_,w in jobs),'chunk_seconds':chunk_seconds,'quality':args.quality,
                'fps':args.fps,'width':int(width),'height':int(height)}
        output.write_text(json.dumps(report,allow_nan=False),encoding='utf-8')
        print('GEM-X benchmark ready',flush=True)
        return
    output.write_text(json.dumps(payload,allow_nan=False),encoding='utf-8')
    print('GEM-X SOMA export ready',flush=True)


def stitch_windows(windows,globs,cams,total,torch,extras=None):
    """Per-window SOMA joint transforms → one sequence of `total` frames.

    Each window's global ("world") system starts from its own origin/heading. Rotate it into
    window 0's system through the static camera (as build_scene does for people), shift it
    to match the previous window over their overlap, then crossfade (slerp/lerp) the
    overlap. Camera-space sequences share the camera already and are only crossfaded.
    Frames outside the track repeat its first/last pose. extras — optional per-window (L, K, 3)
    vectors in that window's world system (e.g. source-joint deltas): rotated like the window and
    linearly crossfaded; returned as a third value."""
    from core import scene_align
    from core.rotations import matmul,transpose
    reference=None;aligned=[];rotations=[]
    for k,((a,b),glob,cam) in enumerate(zip(windows,globs,cams)):
        R=scene_align.camera_to_world(glob[:,0,:3,:3].tolist(),cam[:,0,:3,:3].tolist())
        reference=reference or R
        M=torch.tensor(matmul(reference,transpose(R)),dtype=glob.dtype)
        moved=glob.clone()
        moved[...,:3,:3]=M@glob[...,:3,:3]
        moved[...,:3,3]=glob[...,:3,3]@M.T
        if k:
            pa,pb=windows[k-1]
            frames=range(a,min(pb,b)+1)
            prev=aligned[-1]
            offset=mean_offset([prev[f-pa,0,:3,3].tolist() for f in frames],[moved[f-a,0,:3,3].tolist() for f in frames])
            moved[...,:3,3]+=torch.tensor(offset,dtype=glob.dtype)
        aligned.append(moved)
        if extras is not None:rotations.append(M)
    def join(sequences):
        def blend(x,y,w):
            return torch.stack([torch.tensor(blend_transform(p,q,w),dtype=x.dtype) for p,q in zip(x.tolist(),y.tolist())])
        frames=stitch(windows,lambda k,f:sequences[k][f-windows[k][0]],blend)
        first,last=windows[0][0],windows[-1][1]
        frames=[frames[0]]*first+frames+[frames[-1]]*max(0,total-1-last)
        return torch.stack(frames[:total])
    if extras is None:
        return join(aligned),join(cams)
    moved=[e@M.T.to(e.dtype) for e,M in zip(extras,rotations)]
    frames=stitch(windows,lambda k,f:moved[k][f-windows[k][0]],lambda x,y,w:x+(y-x)*w)
    first,last=windows[0][0],windows[-1][1]
    frames=[frames[0]]*first+frames+[frames[-1]]*max(0,total-1-last)
    return join(aligned),join(cams),torch.stack(frames[:total])


def prepare_identity(layer,params,torch):
    """Фигура участника (форма и масштаб) → T-поза его скелета SOMA."""
    scale=params['scale_params'].mean(0,keepdim=True).cpu()
    identity=params['identity_coeffs'].mean(0,keepdim=True).cpu()
    layer.prepare_identity(identity,scale[:,1:],repose_to_bind_pose=False,global_scale=scale[:,:1])
    return pose_sequence(layer,{'global_orient':torch.zeros(1,3),'body_pose':torch.zeros(1,76*3),'transl':torch.zeros(1,3)},torch)[0]


def pose_sequence(layer,params,torch):
    """Мировые матрицы 77 суставов SOMA по кадрам для параметров (global или incam)."""
    captured=[]
    pose=getattr(layer.batched_skinning,'_mocapgate_pose',layer.batched_skinning.pose)
    layer.batched_skinning._mocapgate_pose=pose
    def capture(*a,**kw):
        vertices,transforms=pose(*a,**kw);captured.append(transforms.detach().cpu());return vertices,transforms
    layer.batched_skinning.pose=capture
    out=[]
    with torch.no_grad():
        for start in range(0,len(params['transl']),32):
            body=params['body_pose'][start:start+32].cpu().reshape(-1,76,3)
            root=params['global_orient'][start:start+32].cpu().reshape(-1,1,3)
            layer.pose(torch.cat([root,body],dim=1),transl=params['transl'][start:start+32].cpu())
            out.append(captured.pop()[:,1:])
    transforms=torch.cat(out)
    if not torch.isfinite(transforms).all():
        raise ValueError('GEM-X returned non-finite joint transforms')
    return transforms


SCENE_ALIASES={'Spine1':'Spine','Spine2':'Spine1','Chest':'Spine2','Neck1':'Neck',
               'HeadEnd':'HeadTop_End','LeftLeg':'LeftUpLeg','LeftShin':'LeftLeg',
               'RightLeg':'RightUpLeg','RightShin':'RightLeg','LeftToeEnd':'LeftToe_End','RightToeEnd':'RightToe_End'}
# суставы ног, которые экспортируются «как у модели в этом кадре» (source_joints) для ретаргета в Studio
SOURCE_JOINTS=('Hips',)+tuple(s+b for s in ('Left','Right') for b in ('UpLeg','Leg','Foot','ToeBase','Toe','Toe_End'))


def scene_names(layer):
    """Имена 77 суставов SOMA (без Root) в именах BVH MoCapGate."""
    return [SCENE_ALIASES.get(str(n),str(n)) for n in layer.rig_data['joint_names'][1:]]


def source_deltas(layer,params,glob,indices,torch,batch=32):
    """(L, K, 3): положение суставов indices на фигуре своего кадра минус на средней фигуре (glob), м.

    GEM-X предсказывает identity_coeffs/scale_params по кадрам; сцена строится на средней фигуре
    (как upstream SomaLayer.temporal_forward), а постобработка контактов upstream (EnDecoder.fk_v2)
    ставит стопы по фигуре кадра. Разница — то, что ретаргет ног в Studio возвращает на место."""
    skinning=layer.batched_skinning
    current=skinning.pose
    skinning.pose=getattr(skinning,'_mocapgate_pose',current)  # без перехвата pose_sequence
    out=[]
    try:
        with torch.no_grad():
            for start in range(0,len(params['transl']),batch):
                sl=slice(start,start+batch)
                scale=params['scale_params'][sl].cpu().float();identity=params['identity_coeffs'][sl].cpu().float()
                layer.prepare_identity(identity,scale[:,1:],repose_to_bind_pose=False,global_scale=scale[:,:1])
                body=params['body_pose'][sl].cpu().reshape(-1,76,3);root=params['global_orient'][sl].cpu().reshape(-1,1,3)
                joints=layer.pose(torch.cat([root,body],dim=1),transl=params['transl'][sl].cpu(),apply_correctives=False)['joints']
                out.append(joints[:,indices].to(glob.dtype)-glob[start:start+len(joints),indices,:3,3])
    finally:
        skinning.pose=current
    return torch.cat(out)


def fk_error(rest,parents,poses,positions,joints,indices,step=1):
    """(max, mean) расстояние, см: FK экспорта (rest + локальные повороты + корень) против суставов сцены.

    Так проверяется, что BVH воспроизводит мировые суставы модели (стопы) по кадрам. Только stdlib."""
    from core.rotations import axis_angle_to_matrix,matmul,mat_vec
    worst=total=0.0;count=0
    for t in range(0,len(poses),max(1,int(step))):
        if joints[t] is None:continue
        G=[None]*len(parents);P=[None]*len(parents)
        for i,p in enumerate(parents):
            R=axis_angle_to_matrix(poses[t][i])
            if p<0:G[i],P[i]=R,list(positions[t])
            else:
                v=mat_vec(G[p],[rest[i][k]-rest[p][k] for k in range(3)])
                G[i]=matmul(G[p],R);P[i]=[P[p][k]+v[k] for k in range(3)]
        for j in indices:
            e=math.dist(P[j],joints[t][j])*100;worst=max(worst,e);total+=e;count+=1
    return worst,(total/count if count else 0.0)


def build_scene(layer,people,width,height,torch,fps=30.0):
    """Все участники в одной сцене: вертикаль по гравитации, место и высота — относительно камеры, пол — Y=0."""
    from core import scene_align
    from core.rotations import matmul,transpose,matrix_to_axis_angle
    names=scene_names(layer)
    parents=[int(p) for p in layer.parents]
    # у каждого участника своя «мировая» система (по гравитации, но со своим поворотом вокруг вертикали):
    # R_p = камера → мир участника; переводим всех в систему первого через камеру: M_p = R_1·R_pᵀ
    feet=scene_align.foot_indices(names);check=scene_align.report_indices(names)
    worlds,reference=[],None
    for p in people:
        r=slice(p['first'],p['last']+1)
        R=scene_align.camera_to_world(p['glob'][r,0,:3,:3].tolist(),p['cam'][r,0,:3,:3].tolist())
        reference=reference or R
        M=torch.tensor(matmul(reference,transpose(R)),dtype=p['glob'].dtype)
        offset=torch.tensor(scene_align.anchor_offset(R,p['cam'][r,0,:3,3].tolist(),p['glob'][r,0,:3,3].tolist()),dtype=p['glob'].dtype)
        p['world']=(p['glob'][:,:,:3,3]+offset)@M.T          # место и высота относительно камеры
        p['world_rot']=M@p['glob'][:,:,:3,:3]                 # повороты в общей системе
        p['M']=M
        worlds.append([frame for i,frame in enumerate(p['world'].tolist()) if p['first']<=i<=p['last']])
    floor=scene_align.floor_height(worlds,feet)
    out=[]
    for p in people:
        world=p['world']-torch.tensor([0.0,floor,0.0])
        neutral_rot=p['neutral'][:,:3,:3].tolist();poses=[]
        for fr in p['world_rot'].tolist():
            w=[matmul(r,transpose(bind)) for r,bind in zip(fr,neutral_rot)]
            poses.append([matrix_to_axis_angle(r if parents[i]<0 else matmul(transpose(w[parents[i]]),r)) for i,r in enumerate(w)])
        joints=world.tolist();cam=p['cam'][:,:,:3,3].tolist()
        out.append({'id':p['id'],'start_frame':p['first'],'end_frame':p['last'],
                    'rest':p['neutral'][:,:3,3].tolist(),'poses':poses,'positions':world[:,0].tolist(),
                    'report_joints':[[frame[j] for j in check] for frame in joints],
                    # 2D-проекция суставов на кадр — только там, где участник действительно был виден
                    'skeleton2d':[scene_align.project(c,p['K']) if p['first']<=i<=p['last'] else None for i,c in enumerate(cam)]})
        rest=out[-1]['rest'];step=max(1,(p['last']-p['first']+1)//300)
        sel=[j if p['first']<=i<=p['last'] else None for i,j in enumerate(joints)]
        worst,mean=fk_error(rest,parents,poses,out[-1]['positions'],sel,feet,step)
        print(format_line('fk_check',{'person':p['id'],'max_foot_error_cm':f'{worst:.3f}','mean_foot_error_cm':f'{mean:.3f}'}),flush=True)
        if p.get('contacts') is not None:out[-1]['contacts']=p['contacts']
        if p.get('source') is not None and p.get('source_index'):
            idx=list(p['source_index'])
            src=world[:,idx]+p['source'].to(world.dtype)@p['M'].T
            out[-1]['source_joints']={'names':[names[i] for i in idx],
                                      'positions':[[[round(v,5) for v in q] for q in frame] for frame in src.tolist()]}
    K=people[0]['K']
    return {'format':'mocapgate.soma/2','fps':float(fps),'camera_mode':'static','names':names,'parents':parents,
            # камера → общий мир (оси камеры OpenCV); центр камеры: R·0 в системе первого участника, минус пол
            'camera':{'height':-floor,'K':K,'width':int(width),'height_px':int(height),
                      'rotation':[list(row) for row in reference],'position':[0.0,-floor,0.0]},'people':out}


def select_tracks(per_frame,total,max_people,min_frames):
    """Устойчивые треки ByteTrack: не короче min_frames кадров, по убыванию суммарной площади рамки.

    per_frame — для каждого кадра список (box xyxy, track_id, score). Демо GEM-X берёт один трек
    с наибольшей площадью; здесь — до max_people, каждый со своим диапазоном кадров.
    """
    from collections import defaultdict
    area=defaultdict(float);seen=defaultdict(list)
    for t,results in enumerate(per_frame):
        for box,tid,score in results:
            area[tid]+=max(0,box[2]-box[0])*max(0,box[3]-box[1]);seen[tid].append((t,box))
    ranked=sorted((tid for tid in area if len(seen[tid])>=min(min_frames,total)),key=lambda tid:-area[tid])
    return [(tid,seen[tid]) for tid in ranked[:max_people]]


def detect_people(demo,cfg,max_people,fps,score_thr=0.5,min_seconds=0.25,max_lost=30):
    """Один проход YOLOX+ByteTrack на всё видео, затем свой bbx.pt для каждого участника.

    fps переводит min_seconds в кадры; max_lost задан в кадрах.

    Дальше препроцесс демо видит готовый bbx.pt и считает 2D-точки и признаки уже по этому человеку.
    """
    import numpy as np
    import torch
    from copy import deepcopy
    from omegaconf import open_dict
    from tqdm import tqdm
    from gem.utils import yolox_detector as det
    print('STAGE Поиск и трекинг людей',flush=True)
    frames=demo.read_video_np(cfg.video_path)  # lazy in the runner: one decoded frame at a time
    total,height,width=len(frames),frames.shape[1],frames.shape[2]
    yolox=det.YOLOXDetector(device='cuda',score_thr=score_thr);tracker=det.ByteTracker(max_lost=max_lost)
    per_frame=[]
    for i in tqdm(range(total),desc='YOLOX+ByteTrack'):
        boxes,scores=yolox.detect(frames[i][...,::-1].copy())
        per_frame.append(tracker.update(boxes,scores))
    del frames,yolox
    # минимальная длительность (по умолчанию четверть секунды) отсекает обрывки трека на краю кадра
    chosen=select_tracks(per_frame,total,max_people,max(3,round(fps*min_seconds)))
    if not chosen:
        raise RuntimeError('GEM-X не нашёл людей в кадре')
    print(f'STAGE Найдено участников: {len(chosen)}',flush=True)
    result=[]
    for tid,observed in chosen:
        bbx=np.zeros((total,4),dtype=np.float32);ids=np.full(total,-1,dtype=np.int32)
        for t,box in observed:bbx[t]=box;ids[t]=tid
        det._interpolate_gaps(bbx,ids,tid,height,width)
        boxes=demo.smooth_bbx_xyxy(torch.from_numpy(bbx).float(),window=3)
        boxes[:,[0,2]]=boxes[:,[0,2]].clamp(0,width-1);boxes[:,[1,3]]=boxes[:,[1,3]].clamp(0,height-1)
        person_cfg=deepcopy(cfg)
        with open_dict(person_cfg):
            person_cfg.output_dir=str(Path(cfg.output_dir)/f'person_{tid}')
            person_cfg.preprocess_dir=str(Path(person_cfg.output_dir)/'preprocess')
        Path(person_cfg.preprocess_dir).mkdir(parents=True,exist_ok=True)
        torch.save({'bbx_xyxy':boxes,'bbx_xys':demo.get_bbx_xys_from_xyxy(boxes,base_enlarge=1.2).float()},
                   person_cfg.paths.bbx)
        result.append((tid,person_cfg,observed[0][0],observed[-1][0]))
    return result


if __name__=='__main__':main()
