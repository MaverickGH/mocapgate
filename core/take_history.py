"""Keep previous completed outputs before a take is processed again."""
import json
from pathlib import Path
from datetime import datetime,timezone
import uuid
import zipfile

OUTPUTS=('bvh','maya_scene','character_scene','character_motion','maya_tools','mesh_file','fbx','overlay','capture_file','face_file','report_file')


def snapshot(take,meta):
    take=Path(take)
    if meta.get('status')!='done' or not meta.get('bvh'):return None
    files=set()
    def add(name):
        if not name:return
        path=(take/name).resolve()
        if not path.is_relative_to(take.resolve()):raise ValueError('путь файла выходит за папку дубля')
        if path.is_file():files.add(path)
    for selected in [meta]+meta.get('people',[]):
        for field in OUTPUTS:add(selected.get(field))
        for field,binary in (('character_motion','motion_file'),('mesh_file','positions_file')):
            if selected.get(field):
                info=json.loads((take/selected[field]).read_text(encoding='utf-8'));add(info.get(binary))
    if not files:return None
    folder=take/'versions';folder.mkdir(exist_ok=True)
    now=datetime.now(timezone.utc);name=now.strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:8]+'.zip'
    pending=folder/(name+'.pending');target=folder/name
    try:
        with zipfile.ZipFile(pending,'w',zipfile.ZIP_DEFLATED) as archive:
            saved={**meta,'options':meta.get('processed_options'), 'options_verified':bool(meta.get('processed_options'))}
            archive.writestr('take.json',json.dumps(saved,ensure_ascii=False,indent=2))
            for path in sorted(files):archive.write(path,path.relative_to(take.resolve()))
        pending.replace(target)
    finally:
        pending.unlink(missing_ok=True)
    return target


def versions(take):
    return [{'file':'versions/'+p.name,'bytes':p.stat().st_size,'name':p.stem}
            for p in sorted((Path(take)/'versions').glob('*.zip'),reverse=True)]


KEEP = ('id', 'name', 'created', 'project', 'tags', 'notes', 'markers', 'input', 'video', 'backend')


def restore(take, file):
    """Вернуть прежнюю версию анимации. Текущая сначала сохраняется в историю — восстановление тоже обратимо."""
    take = Path(take)
    archive_path = (take / file).resolve()
    if not archive_path.is_relative_to((take / 'versions').resolve()) or not archive_path.is_file():
        raise ValueError('Нет такой версии')
    current = json.loads((take / 'take.json').read_text(encoding='utf-8'))
    with zipfile.ZipFile(archive_path) as archive:
        saved = json.loads(archive.read('take.json').decode('utf-8'))
        members = [m for m in archive.namelist() if m != 'take.json']
        for name in members:  # только файлы внутри дубля, без подпапок вне его
            target = (take / name).resolve()
            if not target.is_relative_to(take.resolve()) or name.startswith('versions/'):
                raise ValueError('Версия содержит недопустимый путь: ' + name)
        snapshot(take, current)
        for name in members:
            target = take / name
            target.parent.mkdir(parents=True, exist_ok=True)
            pending = target.with_name(target.name + '.restore')
            pending.write_bytes(archive.read(name))
            pending.replace(target)
    meta = {k: v for k, v in saved.items() if k not in ('options_verified',)}
    meta['options'] = saved.get('options') or current.get('options')
    meta['processed_options'] = saved.get('options') or current.get('processed_options')
    meta.update({k: current[k] for k in KEEP if k in current})  # название, проект, заметки — как сейчас
    meta.update(status='done', error=None, restored_from=Path(file).name)
    tmp = take / 'take.json.restore'
    tmp.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding='utf-8')
    tmp.replace(take / 'take.json')
    return meta
