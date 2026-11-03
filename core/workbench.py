"""Animator diagnostics and reusable rig profiles; independent of recognition models."""
import json
import math
from pathlib import Path
from core import settings
from core.character_rig import read_bvh
from core.rotations import euler_zxy_to_matrix,matrix_to_quat


def motion_events(path):
    names,parents,offsets,channels,rows,step=read_bvh(path)
    events=[];previous=None;root_previous=None
    for f,row in enumerate(rows):
        current=[];cursor=0
        for name,cs in zip(names,channels):
            values=dict(zip(cs,row[cursor:cursor+len(cs)]));cursor+=len(cs)
            current.append(matrix_to_quat(euler_zxy_to_matrix(*(values[c] for c in ('Zrotation','Xrotation','Yrotation')))))
        if previous:
            for i,(a,b) in enumerate(zip(previous,current)):
                angle=math.degrees(2*math.acos(min(1,abs(sum(x*y for x,y in zip(a,b))))))
                speed=angle/step
                # A diagnostic candidate, not confidence or proof of an error.
                if speed>1080 and angle>12:
                    events.append({'frame':f+1,'seconds':round(f*step,6),'kind':'rotation_jump','joint':names[i],'value':round(speed)})
        positions=dict(zip(channels[0],row[:len(channels[0])]))
        root=[positions.get(c,0) for c in ('Xposition','Yposition','Zposition')]
        if root_previous is not None:
            delta=math.dist(root,root_previous)
            if delta>20 and delta/step>800:
                events.append({'frame':f+1,'seconds':round(f*step,6),'kind':'root_jump','joint':names[0],'value':round(delta/step)})
        root_previous=root
        previous=current
    # Cap display data while retaining total candidate count.
    return {'events':events[:1000],'total':len(events),'fps':1/step,'frames':len(rows),'heuristic':True}


def profile_path():return settings.config_dir()/'rig-profiles.json'


def profiles():
    try:return json.loads(profile_path().read_text())
    except FileNotFoundError:return []


def save_profile(body):
    name=str(body.get('name','')).strip()[:80];rig=Path(str(body.get('rig',''))).expanduser()
    mapping=body.get('mapping',{})
    scale=body.get('scale',1);yaw=body.get('yaw',0)
    if not name or rig.suffix.lower()!='.ma' or not rig.is_file():raise ValueError('Укажите название профиля и существующий файл .ma')
    if not isinstance(mapping,dict) or not mapping or len(mapping)>300:raise ValueError('Сопоставление: JSON {"исходная кость":"кость персонажа"}')
    if any(not isinstance(k,str) or not isinstance(v,str) or not k or not v or any(c in k+v for c in '|.\n\r') for k,v in mapping.items()):raise ValueError('Укажите короткие имена костей без пути и атрибутов')
    if len(set(mapping.values()))!=len(mapping):raise ValueError('Каждая кость персонажа должна иметь один источник')
    if type(scale) not in (int,float) or not math.isfinite(scale) or not .01<=scale<=100:raise ValueError('Масштаб: 0.01–100')
    if type(yaw) not in (int,float) or not math.isfinite(yaw) or not -180<=yaw<=180:raise ValueError('Поворот: −180…180°')
    profile={'name':name,'rig':str(rig.resolve()),'mapping':mapping,'scale':scale,'yaw':yaw}
    saved=[p for p in profiles() if p['name']!=name]+[profile]
    path=profile_path();path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(saved,ensure_ascii=False,indent=2));tmp.replace(path)
    return profile


def diagnostics():
    from core.components import status
    import shutil
    c=status();checks=[]
    def add(id,ok,action):checks.append({'id':id,'ok':bool(ok),'action':action})
    add('ffmpeg',c['ffmpeg']['path'],'ffmpeg');ffmpeg=c['ffmpeg']['path']; probe=shutil.which('ffprobe') or (str(Path(ffmpeg).with_name('ffprobe.exe' if str(ffmpeg).endswith('.exe') else 'ffprobe')) if ffmpeg else '')
    add('ffprobe',probe and Path(probe).is_file(),'ffmpeg')
    add('blender',c['blender']['path'],'blender');add('maya',c['maya']['path'],'maya')
    add('gvhmr',c['gvhmr_local']['ready'],'gvhmr');add('gemx',c['gemx']['ready'],'gemx')
    import subprocess
    from core.gvhmr_environment import wsl_prefix
    cfg=settings.load()
    for prefix in ('gvhmr','gemx'):
        py=cfg.get(prefix+'_python')
        if not py: continue
        runtime={'gvhmr_wsl':cfg.get(prefix+'_wsl','')}
        probe_code="import json, torch; print(json.dumps({'cuda':torch.cuda.is_available(),'version':torch.__version__}))"
        command=(wsl_prefix(runtime) if runtime['gvhmr_wsl'] else [])+[py,'-c',probe_code]
        try:
            result=subprocess.run(command,capture_output=True,text=True,timeout=20)
            data=json.loads(result.stdout.strip().splitlines()[-1]) if result.returncode==0 else None
            checks.append({'id':prefix+'-runtime','ok':bool(data) and (prefix!='gvhmr' or data.get('cuda',False)),'action':prefix,
                'detail':data or result.stderr[-1500:]})
        except (OSError,subprocess.TimeoutExpired,ValueError,IndexError) as exc:
            checks.append({'id':prefix+'-runtime','ok':False,'action':prefix,'detail':str(exc)})
    return {'checks':checks,'gpu':c['gpu'],'gvhmr_missing':c['gvhmr_local'].get('missing',[]),
            'note':'Checks describe detected configuration. Real inference must still be tested.'}


def suggest_mapping(rig, bvh):
    """Inspect joint declarations as text; never execute Maya scene content."""
    import re
    from core.maya_export import rig_joint_pairs
    rig=Path(rig)
    if rig.suffix.lower()!='.ma' or not rig.is_file():raise ValueError('Выберите существующий риг .ma')
    if rig.stat().st_size>100*1024*1024:raise ValueError('Для подбора имён нужен .ma размером до 100 МБ')
    names, *_ = read_bvh(bvh)
    target_names=[name.split(':')[-1] for name in re.findall(r'createNode\s+joint\s+[^;]*?-n\s+"([^"\n]+)"',rig.read_text(encoding='utf-8'))]
    if len(set(target_names))!=len(target_names):raise ValueError('Имена суставов в риге неоднозначны')
    pairs=rig_joint_pairs({n:n for n in names},{n:n for n in target_names})
    return {'mapping':dict(pairs),'source_joints':names,'target_joints':target_names,'unmatched':[n for n in names if n not in dict(pairs)]}
