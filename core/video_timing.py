"""Video timestamps and animation resampling; no array-library dependency."""
import copy
from fractions import Fraction
import json
import math
from pathlib import Path
import shutil
import subprocess


def run_media(command, what):
    """ffmpeg / ffprobe: при сбое — короткая причина вместо длинной командной строки."""
    try:
        return subprocess.run(command,capture_output=True,text=True,encoding='utf-8',errors='replace',check=True)
    except FileNotFoundError:
        raise RuntimeError(f'{what}: не найден {Path(str(command[0])).name}. Установите ffmpeg в разделе «Модели и инструменты».') from None
    except subprocess.CalledProcessError as exc:
        tail=[l.strip() for l in (exc.stderr or '').splitlines() if l.strip()][-3:]
        raise RuntimeError(f'{what} (код {exc.returncode})'+(': '+' · '.join(tail) if tail else '')) from None


def probe(video, cfg=None):
    from core.managed_tools import find_ffmpeg
    ffmpeg=find_ffmpeg()
    executable=shutil.which('ffprobe') or (str(Path(ffmpeg).with_name('ffprobe.exe' if str(ffmpeg).endswith('.exe') else 'ffprobe')) if ffmpeg else '')
    prefix=[executable]
    if cfg and cfg.get('gvhmr_wsl'):
        from core.gvhmr_environment import wsl_prefix,linux_path
        prefix=wsl_prefix(cfg)+['ffprobe'];video=linux_path(video,cfg)
    elif not executable or not Path(executable).is_file():
        from core.managed_tools import install_ffprobe
        executable=install_ffprobe();prefix=[executable]
    result=run_media(prefix+['-v','error','-select_streams','v:0','-show_entries',
        'stream=avg_frame_rate,r_frame_rate,duration:frame=best_effort_timestamp_time,pkt_duration_time,duration_time:format=duration',
        '-show_frames','-of','json',str(video)],'Не удалось прочитать видео')
    data=json.loads(result.stdout or '{}')
    if not data.get('streams'):raise RuntimeError('В файле нет видеодорожки — выберите другое видео')
    stream=data['streams'][0];frames=data.get('frames',[])
    times=[float(f['best_effort_timestamp_time']) for f in frames if 'best_effort_timestamp_time' in f]
    if not times:raise ValueError('Видео не содержит временных меток кадров')
    start=times[0];times=[t-start for t in times]
    rate=0
    for key in ('avg_frame_rate','r_frame_rate'):
        try:rate=float(Fraction(stream.get(key) or '0'))
        except (ValueError,ZeroDivisionError):continue
        if rate>0:break
    if rate<=0:rate=(len(times)-1)/times[-1] if times[-1]>0 else 30
    duration=float(stream.get('duration') or 0) or times[-1]+float(frames[-1].get('duration_time') or frames[-1].get('pkt_duration_time') or 1/rate)
    deltas=[b-a for a,b in zip(times,times[1:])]
    return {'fps':rate,'duration':duration,'frames':len(times),'timestamps':times,
            'vfr':bool(deltas and max(deltas)-min(deltas)>max(.0001, .01/rate))}


def scale_filter(max_px):
    """Длинная сторона не больше max_px (чётные размеры для x264); 0 — исходный размер.
    4K-видео целиком в памяти модели — ~13 ГБ на 550 кадров: для распознавания хватает 1920 px."""
    if not max_px:
        return ''
    m=int(max_px)
    return (f",scale='if(gte(iw,ih),min(iw,{m}),-2)':'if(gte(iw,ih),-2,min(ih,{m}))'"
            ",scale=trunc(iw/2)*2:trunc(ih/2)*2")


def normalize(video, output, fps, cfg=None, max_px=0):
    from core.managed_tools import find_ffmpeg
    ffmpeg=find_ffmpeg()
    if not ffmpeg and not (cfg and cfg.get('gvhmr_wsl')):
        raise RuntimeError('Не найден ffmpeg — установите его в «Модели и инструменты».')
    command=[ffmpeg]
    final=Path(output);part=final.with_name(final.stem+'.part'+final.suffix)  # прерванное перекодирование не выдаётся за готовое
    target=part
    if cfg and cfg.get('gvhmr_wsl'):
        from core.gvhmr_environment import wsl_prefix,linux_path
        command=wsl_prefix(cfg)+['ffmpeg'];video=linux_path(video,cfg);target=linux_path(part,cfg)
    run_media(command+['-y','-loglevel','error','-i',str(video),'-vf',f'setpts=PTS-STARTPTS,fps={fps}'+scale_filter(max_px),
        '-c:v','libx264','-preset','veryfast','-crf','18','-pix_fmt','yuv420p','-an',str(target)],'Не удалось перекодировать видео')
    part.replace(final)


def blend(a,b,u):
    if a is None or b is None or isinstance(a,bool):return copy.deepcopy(a if u<.5 else b)
    if isinstance(a,dict):return {k:blend(v,b.get(k,v),u) for k,v in a.items()}
    if isinstance(a,list):return [blend(x,y,u) for x,y in zip(a,b)]
    if isinstance(a,(float,int)):return a+(b-a)*u
    return copy.deepcopy(a if u<.5 else b)


def retime_review(overlay, report, target, length):
    """Keep review frames on the exported animation clock, including missing observations."""
    source=float(overlay['fps']);scale=target/source
    def samples(values):
        return [copy.deepcopy(values[min(len(values)-1,int(i/scale))]) for i in range(length)] if values else values
    overlay={**overlay,'fps':target,'skeleton':samples(overlay['skeleton'])}
    if overlay.get('detected'):
        overlay['detected']=samples(overlay['detected'])
    for key in ('start_frame','end_frame'):
        if key in overlay:overlay[key]=min(length-1,max(0,round(overlay[key]*scale)))
    if report:
        report={**report,'per_frame':samples(report.get('per_frame')),'fps':target,'frames':length,
                'duration':round(length/target,2)}
    return overlay,report


def rotation(a,b,u):
    def quaternion(v):
        angle=math.sqrt(sum(x*x for x in v));scale=math.sin(angle/2)/angle if angle>1e-12 else .5
        return [math.cos(angle/2),*[x*scale for x in v]]
    q,r=quaternion(a),quaternion(b);dot=sum(x*y for x,y in zip(q,r))
    if dot<0:r=[-x for x in r];dot=-dot
    if dot>.9995:v=[x+(y-x)*u for x,y in zip(q,r)]
    else:
        angle=math.acos(min(1,dot));v=[(x*math.sin((1-u)*angle)+y*math.sin(u*angle))/math.sin(angle) for x,y in zip(q,r)]
    norm=math.sqrt(sum(x*x for x in v));v=[x/norm for x in v];length=math.sqrt(sum(x*x for x in v[1:]))
    angle=2*math.atan2(length,v[0]);return [x*angle/length if length>1e-12 else 0 for x in v[1:]]


def resample_person(person,target,duration=None):
    source=float(person['fps']);params=person['params'];count=len(params['transl'])
    duration=duration or count/source;length=max(1,round(duration*target))
    result=copy.deepcopy(person)
    def series(values,angular=False):
        output=[]
        for i in range(length):
            p=min(count-1,i*source/target);a=int(p);b=min(count-1,a+1);u=p-a
            if angular:
                output.append(sum((rotation(values[a][j:j+3],values[b][j:j+3],u) for j in range(0,len(values[a]),3)),[]))
            else:output.append(blend(values[a],values[b],u))
        return output
    def update(p):
        for key in ('global_orient','body_pose','transl','found','betas','jaw_pose','leye_pose','reye_pose','left_hand_pose','right_hand_pose','expression'):
            value=p.get(key)
            if isinstance(value,list) and len(value)==count and (key!='betas' or isinstance(value[0],list)):
                p[key]=series(value,key in ('global_orient','body_pose','jaw_pose','leye_pose','reye_pose','left_hand_pose','right_hand_pose'))
        if isinstance(p.get('incam'),dict):update(p['incam'])
        if p.get('camera',{}).get('pelvis'):p['camera']['pelvis']=series(p['camera']['pelvis'])
        p['fps']=target
    update(result['params']);result['fps']=target
    if isinstance(result.get('params'),dict):
        for key in ('multiview_provenance','multiview_source_frame_indices'):
            value=result['params'].get(key)
            if isinstance(value,list) and len(value)==count:
                result['params'][key]=series(value)
    # кадры появления/ухода участника — в новой частоте (иначе при 60 FPS человек «пропадал» на середине видео)
    for key in ('start_frame','end_frame'):
        if isinstance(result.get(key),(int,float)):result[key]=min(length-1,max(0,round(result[key]*target/source)))
    if result.get('landmarks'):
        result['landmarks']['frames']=series(result['landmarks']['frames']);result['landmarks']['fps']=target
    if result.get('details') is not None:result['details']=series(result['details'])
    return result
