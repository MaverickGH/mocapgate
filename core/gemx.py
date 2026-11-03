"""Managed GEM-X environment and portable worker invocation."""
import json
import os
from pathlib import Path
import subprocess
import sys
from core import settings
from core.gvhmr_environment import (installed_distros, select_distro, wsl_prefix, linux_path, wsl_output, wsl_failure,
                                    unfinished_distros, probe_wsl, require_disk, setup_log, failure_reason, APT)

ROOT=Path(__file__).resolve().parents[1]


def runtime(cfg=None):
    cfg=cfg or settings.load()
    return {'gvhmr_dir':cfg.get('gemx_dir',''),'gvhmr_python':cfg.get('gemx_python',''),
            'gvhmr_wsl':cfg.get('gemx_wsl','')}


def ready(cfg=None):
    cfg=cfg or settings.load()
    repo=cfg.get('gemx_dir');py=cfg.get('gemx_python')
    if not repo or not py:return False
    required=('scripts/demo/demo_soma_onnx.py','inputs/onnx/gem_denoiser.onnx',
        'inputs/onnx/vitpose.onnx','inputs/onnx/sam3db_backbone.onnx',
        'inputs/checkpoints/sam-3d-body-dinov3/sam3d_body.ckpt','inputs/mhr_data/mhr_model.pt',
        'inputs/pretrained/gem_soma.ckpt','inputs/soma_assets/SOMA_neutral.npz')
    if cfg.get('gemx_wsl'):
        check="from pathlib import Path; import sys; p=Path("+repr(repo)+"); sys.exit(not all((p/f).is_file() for f in "+repr(required)+"))"
        def probe():
            try:
                # A stopped WSL distribution can take more than ten seconds to boot.
                return subprocess.run(wsl_prefix(runtime(cfg))+[py,'-c',check],capture_output=True,timeout=30).returncode==0
            except subprocess.TimeoutExpired:return None
            except OSError:return False
        from core.components import remembered
        return bool(remembered(('gemx',cfg['gemx_wsl'],py,repo),probe))
    return Path(py).is_file() and all((Path(repo)/f).is_file() for f in required)


def setup(log=print):
    cfg=settings.load();script=ROOT/'scripts/setup_gemx.py'
    distro=''
    command=[sys.executable,str(script)]
    if os.name=='nt':
        from core import components
        if not components.gpu_info().get('cuda'):
            raise RuntimeError('GEM-X на Windows требует NVIDIA с CUDA. Установите драйвер NVIDIA, перезапустите Studio и проверьте «Модели и инструменты».')
        names=installed_distros()
        listing=subprocess.run(['wsl.exe','--list','--verbose'],capture_output=True,timeout=30)
        unfinished=unfinished_distros(listing.stdout)
        if cfg.get('gemx_wsl') in unfinished:
            raise RuntimeError('Выбранный WSL ещё Installing. Завершите первый запуск или выберите готовый дистрибутив.')
        distro=select_distro(cfg.get('gemx_wsl',''),[n for n in names if n not in unfinished])
        if not distro: raise RuntimeError('Установите и запустите Ubuntu / WSL2 в разделе моделей.')
        wsl={'gvhmr_wsl':distro}
        probe=probe_wsl(wsl_prefix(wsl))
        if probe.returncode:
            raise RuntimeError(wsl_failure(wsl_output(probe.stderr or probe.stdout)))
        if not cfg.get('gemx_dir'):require_disk(30,'GEM-X')
        listing=subprocess.run(['wsl.exe','--list','--verbose'],capture_output=True,timeout=30)
        rows=[line.replace('*','',1).split() for line in wsl_output(listing.stdout).splitlines()]
        selected=[r for r in rows if r and r[0].casefold()==distro.casefold()]
        if selected and selected[0][-1]!='2':
            subprocess.run(['wsl.exe','--set-version',distro,'2'],check=True,timeout=600)
        root=['wsl.exe','--distribution',distro,'--user','root','--exec']
        log('Подготавливаю зависимости GEM-X в WSL…')
        subprocess.run(root+APT+['update'],check=True)
        subprocess.run(root+['env','DEBIAN_FRONTEND=noninteractive']+APT+['install','-y',
            'python3','python3-venv','python3-dev','git','git-lfs','ffmpeg','build-essential','libgl1','libegl1','libglib2.0-0'],check=True)
        command=wsl_prefix(wsl)+['python3',linux_path(script,wsl)]
    result=None;write=setup_log(log);tail=[]
    env={**os.environ,'PYTHONUTF8':'1','HF_HUB_DISABLE_PROGRESS_BARS':'1'}
    with subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace',env=env) as proc:
        for line in proc.stdout:
            write(line.rstrip());tail=(tail+[line.rstrip()])[-200:]
            if line.startswith('MOCAPGATE_GEMX '): result=json.loads(line.split(' ',1)[1])
        code=proc.wait()
    if code:
        reason=failure_reason(tail)
        raise RuntimeError('Установка GEM-X не завершена'+(': '+reason if reason else f' (код {code})')+'. Повторная установка продолжит скачивание.')
    if not result: raise RuntimeError('GEM-X setup did not return a verified environment')
    settings.save({**result,'gemx_wsl':distro})
    return 0
