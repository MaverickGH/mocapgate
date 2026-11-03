"""Non-destructive, frame-exact clip export using the final capture BVH."""
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def validate(first,last,count):
    if type(first) is not int or type(last) is not int or not 1<=first<=last<=count:
        raise ValueError('Диапазон должен содержать целые кадры от 1 до конца дубля')


EDIT_KEYS={'mirror':bool,'speed':float,'ease_in':float,'ease_out':float,'yaw':float,'scale':float,'floor':bool}


def edit_options(edit):
    """Правки фрагмента из окна → проверенные значения (пустые — без изменений)."""
    edit={k:EDIT_KEYS[k](v) for k,v in (edit or {}).items() if k in EDIT_KEYS and v not in (None,'')}
    if not 0.1<=edit.get('speed',1)<=10:raise ValueError('Скорость: 0,1…10×')
    if not 0.01<=edit.get('scale',1)<=100:raise ValueError('Масштаб пути: 0,01…100')
    if not (0<=edit.get('ease_in',0)<=10 and 0<=edit.get('ease_out',0)<=10):raise ValueError('Плавный вход/выход: 0…10 с')
    if not -360<=edit.get('yaw',0)<=360:raise ValueError('Поворот: −360…360°')
    return {k:v for k,v in edit.items() if v not in (False,0.0) and not (k in ('speed','scale') and v==1.0)}


def export(take,first,last,person=None,inplace=False,fbx=False,loop=False,root_motion=False,edit=None):
    from core import pipeline,components
    from core.character_rig import read_bvh,build
    from core.skeleton import Joint
    from core.maya_export import write as write_maya
    take=Path(take);meta=pipeline.person_meta(pipeline.read_meta(take),person)
    if meta.get('status')!='done' or not meta.get('bvh'):raise ValueError('Сначала обработайте дубль')
    original=take/meta['bvh'];names,parents,offsets,channels,rows,step=read_bvh(original)
    validate(first,last,len(rows));rows=rows[first-1:last]
    rate=float(meta['fps'])
    if not math.isfinite(rate) or rate<=0 or abs(rate-1/step)>1e-3:raise ValueError('FPS дубля не совпадает с BVH; обработайте дубль заново')
    pipeline.emit('clip',f'Готовлю кадры {first}–{last}…',.1)
    if inplace:
        for row in rows:
            for channel in ('Xposition','Zposition'):row[channels[0].index(channel)]=0.
    header=original.read_text(encoding='utf-8').split('MOTION',1)[0]
    edit=edit_options(edit)
    archive_name=f'clip-{person or 1}-{first}-{last}'+('-inplace' if inplace else '')+('-loop' if loop else '')+('-rootmotion' if root_motion else '')+('-mirror' if edit.get('mirror') else '')+'-'+uuid.uuid4().hex[:8]+'.zip'
    with tempfile.TemporaryDirectory(dir=take,prefix='.clip-') as folder:
        folder=Path(folder);bvh=folder/'capture.bvh'
        bvh.write_text(header+f'MOTION\nFrames: {len(rows)}\nFrame Time: {step:.12f}\n'+'\n'.join(' '.join(f'{v:.12g}' for v in row) for row in rows)+'\n',encoding='utf-8')
        nodes=[Joint(n,tuple(offsets[i])) for i,n in enumerate(names)]
        for i,parent in enumerate(parents):
            if parent>=0:nodes[parent].children.append(nodes[i])
        frames=[]
        for row in rows:
            frame={};cursor=0
            for name,cs in zip(names,channels):
                values=dict(zip(cs,row[cursor:cursor+len(cs)]));cursor+=len(cs)
                frame[name]={'rot':tuple(values[c] for c in ('Zrotation','Xrotation','Yrotation'))}
                if name==names[0]:frame[name]['pos']=tuple(values[c] for c in ('Xposition','Yposition','Zposition'))
            frames.append(frame)
        seam=None
        mirrored=False;speed=1.0
        if loop or root_motion or edit:  # игровые клипы и правки: цикл, Root, зеркало, скорость, вход/выход, поворот
            from core import anim_tools,anim_edit
            from core.studio_tools import read_motion  # имена с mixamorig: и End Site — как в исходном BVH
            source,all_frames,_=read_motion(original)
            nodes=[source];frames=all_frames[first-1:last]
            if inplace:
                for frame in frames:
                    pos=frame[source.name]['pos'];frame[source.name]['pos']=(0.,pos[1],0.)
            if edit.get('yaw') or edit.get('scale') or edit.get('floor'):
                frames=anim_edit.transform(source,frames,scale=edit.get('scale',1.0),yaw_deg=edit.get('yaw',0.0),floor_to_zero=edit.get('floor',False))
            if edit.get('mirror'):
                source,frames=anim_edit.mirror(source,frames);nodes=[source];mirrored=True
            if edit.get('speed'):
                pipeline.emit('clip',f"Меняю скорость ×{edit['speed']:g}…",.15)
                frames,_=anim_edit.retime(frames,rate,speed=edit['speed']);speed=edit['speed']
            if edit.get('ease_in') or edit.get('ease_out'):
                frames=anim_edit.ease(source,frames,rate,fade_in=edit.get('ease_in',0.0),fade_out=edit.get('ease_out',0.0))
            if loop:
                pipeline.emit('clip','Делаю бесшовный цикл…',.2)
                frames,seam=anim_tools.make_loop(nodes[0],frames,rate,keep_travel=not inplace)
            root=nodes[0]
            if root_motion:
                root,frames=anim_tools.extract_root_motion(nodes[0],frames)
            nodes=[root]
            bvh.write_text(anim_tools.write_bvh(root,frames,step),encoding='utf-8')  # у Hips свои каналы позиции
        write_maya(folder/'capture.ma',nodes[0],frames,rate)
        face=None
        source_face=take/meta['face_file'] if meta.get('face_file') else None
        if source_face and source_face.is_file():  # мимика — те же кадры, нумерация фрагмента с 1
            from core.face_export import write_csv,append_csv_to_maya
            lines=source_face.read_text(encoding='utf-8').splitlines()
            names=lines[0].split(',')[2:]
            values=[[float(v) for v in row.split(',')[2:]] for row in lines[1:] if row][first-1:last]
            if mirrored:  # зеркало: eyeBlinkLeft ↔ eyeBlinkRight и т.п.
                swap=lambda n:n.replace('Left','\0').replace('Right','Left').replace('\0','Right')
                order=[names.index(swap(n)) if swap(n) in names else i for i,n in enumerate(names)]
                values=[[row[j] for j in order] for row in values]
            if speed!=1.0 and values:  # мимика — по тем же моментам времени, что и тело
                count=len(frames)+(seam['blend_frames'] if seam else 0)
                src=values;values=[]
                for k in range(count):
                    x=k*(len(src)-1)/max(1,count-1);i=min(int(x),len(src)-2) if len(src)>1 else 0;w=x-i
                    values.append([a+(b-a)*w for a,b in zip(src[i],src[min(i+1,len(src)-1)])])
            if seam:  # цикл начинается с кадра N; последние N кадров плавно переходят в начало — как тело
                n=seam['blend_frames'];head=values[:n];values=values[n:]
                for j in range(min(n,len(values))):
                    w=(j+1)/(n+1);w=w*w*(3-2*w);row=values[len(values)-n+j]
                    values[len(values)-n+j]=[a+(b-a)*w for a,b in zip(row,head[j])]
            if len(values)==len(frames):
                face=folder/'capture.face.csv';write_csv(face,names,values,rate)
                append_csv_to_maya(face,folder/'capture.ma')
        audio=None
        source_audio=take/meta['audio'] if meta.get('audio') else None
        ffmpeg=components.find_ffmpeg()
        if source_audio and source_audio.is_file() and ffmpeg and not loop:  # звук участка; в цикле звук не зацикливается — без него
            tempo=[]
            k=speed
            while k>2.0+1e-9:tempo.append('atempo=2.0');k/=2.0
            while k<0.5-1e-9:tempo.append('atempo=0.5');k/=0.5
            if abs(k-1)>1e-6:tempo.append(f'atempo={k:.6f}')
            r=subprocess.run([ffmpeg,'-y','-loglevel','error','-ss',f'{(first-1)/rate:.6f}','-t',f'{(last-first+1)/rate:.6f}','-i',str(source_audio),
                              *(['-filter:a',','.join(tempo)] if tempo else []),'-c:a','pcm_s16le',str(folder/'capture.wav')],capture_output=True,timeout=600)
            audio=(folder/'capture.wav') if r.returncode==0 and (folder/'capture.wav').is_file() else None
        if meta.get('character_scene') and not root_motion:  # Man_Rig без кости Root — сцена со скелетом записи
            pipeline.emit('character','Создаю сцену персонажа для фрагмента…',.3)
            build(bvh,folder/'character.ma',rate)
            if face:append_csv_to_maya(face,folder/'character.ma')
        if fbx:
            blender=components.find_blender()
            if not blender:raise ValueError('Для FBX нужен Blender')
            code,lines=pipeline._run_streaming([blender,'-b','--factory-startup','-P',str(ROOT/'core/blender_io.py'),'--','--bvh',str(bvh),'--fbx',str(folder/'capture.fbx'),'--name','MoCapGate_clip',*(['--face',str(face)] if face else [])],'fbx')
            if code or not (folder/'capture.fbx').is_file():raise RuntimeError(pipeline.failure_summary('Blender', code, lines) if code else 'Blender не создал FBX')
        info={'format':'mocapgate.clip/1','take':take.name,'person':person,'backend':meta.get('backend'),
              'first_frame':first,'last_frame':last,'frames':len(rows),'fps':rate,'duration':len(rows)/rate,
              'source_fps':meta.get('source_fps'),'recognition_fps':meta.get('recognition_fps'),
              'root':'inplace-horizontal' if inplace else 'original','fbx_content':('capture skeleton'+(' + face blend shapes' if face else '')) if fbx else None,
              'face_curves':'capture.face.csv' if face else None,'audio':'capture.wav' if audio else None,'loop':bool(loop),'root_motion':bool(root_motion),'edit':edit,
              'loop_seam':seam}
        (folder/'clip.json').write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding='utf-8')
        target=take/archive_name;staged=folder/'archive.zip'
        with zipfile.ZipFile(staged,'w',zipfile.ZIP_DEFLATED) as archive:
            for file in sorted(folder.iterdir()):
                if file.suffix in ('.bvh','.ma','.fbx','.csv','.wav') or file.name=='clip.json' or file.name.endswith('.maya-tools.py'):archive.write(file,file.name)
        staged.replace(target)
    whole=pipeline.read_meta(take);whole['clip_archive']=archive_name;whole['clip_info']={**info,'archive':archive_name};whole.setdefault('clips',[]).append(whole['clip_info']);pipeline.write_meta(take,whole)
    pipeline.emit('done',f'Фрагмент: {first}–{last}, {rate:g} FPS',1)
    return target


if __name__=='__main__':
    try:
        take,first,last,person,inplace,fbx,*extra=sys.argv[1:]
        loop,root_motion,edit=(extra+['0','0','{}'])[:3]
        export(take,int(first),int(last),int(person) or None,inplace=='1',fbx=='1',loop=='1',root_motion=='1',json.loads(edit))
    except Exception as exc:
        from core.pipeline import emit
        emit('error',str(exc));raise SystemExit(1)
