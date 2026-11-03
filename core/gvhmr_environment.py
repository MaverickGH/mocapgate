"""Host-side GVHMR environment and Windows/WSL argument routing."""
from __future__ import annotations
import json
import ast
import struct
import os
import re
import time
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DISTRO = 'Ubuntu'
APT = ['apt-get', '-o', 'DPkg::Lock::Timeout=600', '-o', 'Acquire::Retries=3',
       '-o', 'Acquire::http::Timeout=30', '-o', 'Acquire::https::Timeout=30']
WSL_HUNG = 'WSL не отвечает — перезапустите компьютер или выполните в PowerShell: wsl --shutdown'
INSTALLING = ('installing', 'установка', 'устанавливается', 'installiert', 'installation', 'instalando', 'installazione')


class SetupPending(RuntimeError):
    """Windows setup requires an external step before the job can continue."""


def wsl_output(raw):
    if isinstance(raw, str):
        return raw.replace('\x00', '')
    encoding = 'utf-16-le' if b'\x00' in raw or raw.startswith(b'\xff\xfe') else 'utf-8'
    return raw.decode(encoding, errors='replace').lstrip('\ufeff').replace('\x00', '')


def windows_wsl_diagnostics():
    """Read feature state and recent servicing failures; never repair or delete adapters."""
    script = r"""[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $ErrorActionPreference='Continue';
    'Microsoft-Windows-Subsystem-Linux','VirtualMachinePlatform' | ForEach-Object {Get-WindowsOptionalFeature -Online -FeatureName $_} | Select-Object FeatureName,State | Format-List;
    Get-WinEvent -FilterHashtable @{LogName='Setup';StartTime=(Get-Date).AddDays(-3)} -MaxEvents 15 -ErrorAction SilentlyContinue | Select-Object TimeCreated,Id,Message | Format-List;
    Get-WinEvent -FilterHashtable @{LogName='Application';StartTime=(Get-Date).AddDays(-3);Id=1000} -MaxEvents 30 -ErrorAction SilentlyContinue | Where-Object {$_.Message -match 'NetSetupSvc|NetSetupEngine'} | Select-Object TimeCreated,Message | Format-List;
    Get-Content $env:windir\Logs\CBS\CBS.log -Tail 2000 -ErrorAction SilentlyContinue | Select-String '0x800706be|0x800f0922|vms_pp|NetSetupAI' | Select-Object -Last 12
    """
    try:
        result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', script],
                                capture_output=True, timeout=45)
        return wsl_output(result.stdout + result.stderr)[-12000:]
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 'Диагностика Windows недоступна: ' + str(exc)


def wsl_failure(message):
    missing = any(code in message.lower() for code in ('0x80040321', 'wsl_e_wsl_optional_component_required'))
    if missing:
        return ('Компонент WSL выключен или Windows откатила его включение.\n' + message +
                '\nПроверьте компоненты Windows WSL и Virtual Machine Platform. Если после перезагрузки они снова выключены, проверьте CBS.log и службы установки Windows.\n' + windows_wsl_diagnostics())
    return message


def installed_distros():
    result = subprocess.run(['wsl.exe', '--list', '--quiet'], capture_output=True, timeout=30)
    if result.returncode:
        message = wsl_output(result.stderr or result.stdout)
        if any(value in message.lower() for value in ('wsl_e_default_distro_not_found', 'no installed distributions', 'нет установленных дистрибутивов')):
            return []
        raise RuntimeError('Не удалось получить список WSL: ' + wsl_failure(message))
    return [line.strip() for line in wsl_output(result.stdout).splitlines() if line.strip()]


def select_distro(requested, names):
    if requested:
        match = next((name for name in names if name.casefold() == requested.casefold()), None)
        if match:
            return match
        # Migrate the previous automatic default to an existing Ubuntu installation.
        if requested != 'Ubuntu-22.04':
            raise RuntimeError('Дистрибутив WSL не найден: ' + requested + '. Установлены: ' + ', '.join(names))
    # Только Ubuntu/Debian: docker-desktop и прочие служебные дистрибутивы не подходят для установки.
    for prefix in ('ubuntu', 'debian'):
        match = next((name for name in names if name.casefold().startswith(prefix)), None)
        if match:
            return match
    return ''


def unfinished_distros(raw):
    """Дистрибутивы в состоянии Installing, включая локализованный вывод wsl --list --verbose."""
    found = []
    for line in wsl_output(raw).splitlines():
        row = line.strip().lstrip('*').split()
        if len(row) >= 3 and row[-1].isdigit():
            state = ' '.join(row[1:-1]).casefold()
            if any(word in state for word in INSTALLING):
                found.append(row[0])
    return found


def probe_wsl(prefix):
    """wsl --exec true; зависший WSL — понятная подсказка вместо TimeoutExpired."""
    try:
        return subprocess.run(prefix + ['true'], capture_output=True, timeout=90)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(WSL_HUNG) from exc


def require_disk(gigabytes, label):
    """Windows: место на диске, где лежит виртуальный диск WSL (по умолчанию — профиль пользователя)."""
    folder = os.environ.get('LOCALAPPDATA') or str(Path.home())
    try:
        free = shutil.disk_usage(folder).free
    except OSError:
        return
    if free < gigabytes * 1024**3:
        raise RuntimeError(f'{label}: нужно не меньше {gigabytes} ГБ свободного места на диске {Path(folder).anchor or folder} '
                           f'(свободно {free // 1024**3} ГБ). Освободите место и повторите установку.')


def check_gpu_generation():
    """RTX 50 (Blackwell, sm_120) не поддерживается сборкой torch 2.3 / cu121 из requirements GVHMR."""
    capability = compute_capability()
    if capability and capability[0] >= 12:
        raise RuntimeError(f'Видеокарта NVIDIA с compute capability {capability[0]}.{capability[1]} (RTX 50-серия) не поддерживается '
                           'PyTorch 2.3 / CUDA 12.1, на котором работает GVHMR. Используйте GEM-X или GVHMR · Colab.')


def compute_capability():
    smi = shutil.which('nvidia-smi')
    if not smi:
        return None
    try:
        out = subprocess.run([smi, '--query-gpu=compute_cap', '--format=csv,noheader'],
                             capture_output=True, text=True, timeout=15).stdout
        major, minor = out.strip().splitlines()[0].strip().split('.')
        return int(major), int(minor)
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        return None


PROGRESS = re.compile(r'\d+%\||\d[\d.]*\s*[kMG]i?B/s|\d+(\.\d+)?\s*it/s')


def setup_log(log, interval=5.0):
    """Строки прогресса tqdm/pip (\\r превращается в перевод строки) — не чаще раза в interval секунд."""
    last = [0.0]
    def write(line):
        line = line.rstrip().rsplit('\r', 1)[-1]
        if PROGRESS.search(line):
            now = time.monotonic()
            if now - last[0] < interval:
                return
            last[0] = now
        else:
            last[0] = 0.0
        log(line)
    return write


def failure_reason(lines):
    """Последняя строка вида «SomethingError: …» из журнала установки."""
    for line in reversed(lines):
        if re.match(r'^\s*(\w+\.)*\w*(Error|Exception)\b.*:', line):
            return line.strip()[-500:]
    return ''



def wsl_prefix(cfg):
    return ['wsl.exe', '--distribution', cfg['gvhmr_wsl'], '--exec']


def linux_path(path, cfg):
    result = subprocess.run(wsl_prefix(cfg) + ['wslpath', '-a', '-u', str(Path(path).resolve())],
                            capture_output=True, encoding='utf-8', check=True, timeout=30)
    value = result.stdout.strip()
    if not value.startswith('/') or '\n' in value:
        raise RuntimeError('WSL не смог преобразовать путь: ' + str(path))
    return value


def stop_wsl_work(folder, cfg=None):
    """Windows: taskkill закрывает wsl.exe, но процесс модели внутри Linux продолжает работать и держит
    GPU и файлы дубля. Останавливаем в дистрибутивах GVHMR / GEM-X всё, что запущено с путями этого дубля."""
    if os.name != 'nt' or not folder:
        return 0
    import re
    if cfg is None:
        from core import settings
        cfg = settings.load()
    stopped = 0
    for distro in {cfg.get('gvhmr_wsl'), cfg.get('gemx_wsl')} - {'', None}:
        try:
            path = linux_path(folder, {'gvhmr_wsl': distro})
            result = subprocess.run(['wsl.exe', '--distribution', distro, '--exec', 'pkill', '-KILL', '-f', '--',
                                     re.escape(path.rstrip('/') + '/')], capture_output=True, timeout=30)  # «…-walk/», не «…-walk-2»
            stopped += result.returncode == 0  # pkill: 0 — остановлен хотя бы один, 1 — ничего не найдено
        except (OSError, subprocess.SubprocessError, RuntimeError):
            pass
    return stopped


def worker_command(cfg, worker, *paths):
    if cfg.get('gvhmr_wsl'):
        return wsl_prefix(cfg) + [cfg['gvhmr_python'], linux_path(worker, cfg),
                                  *[linux_path(p, cfg) for p in paths]]
    return [cfg['gvhmr_python'], str(worker), *map(str, paths)]


def validate_model(path):
    try:
        with zipfile.ZipFile(path) as archive:
            required = {'v_template.npy', 'shapedirs.npy', 'posedirs.npy', 'J_regressor.npy',
                        'weights.npy', 'kintree_table.npy'}
            if not required.issubset(set(archive.namelist())):
                raise ValueError('Нужна SMPL-X NEUTRAL в формате NPZ, а не SMPL или архив загрузки.')
            if sum(item.file_size for item in archive.infolist()) > 1024**3:
                raise ValueError('Файл модели слишком большой.')
            with archive.open('v_template.npy') as vertices:
                prefix = vertices.read(8)
                if prefix[:6] != b'\x93NUMPY' or prefix[6] not in (1,2,3):
                    raise ValueError('Неверный массив вершин SMPL-X.')
                width = 2 if prefix[6] == 1 else 4
                length = int.from_bytes(vertices.read(width), 'little')
                if length > 8192:
                    raise ValueError('Неверный заголовок модели.')
                try:
                    shape = ast.literal_eval(vertices.read(length).decode('latin1'))['shape']
                except (ValueError, SyntaxError, KeyError) as exc:
                    raise ValueError('Неверный заголовок модели.') from exc
                if shape != (10475,3):
                    raise ValueError('Нужна модель SMPL-X (10475 вершин), а не SMPL/SMPL-H.')
            if archive.testzip() is not None:
                raise ValueError('Файл SMPL-X повреждён.')
    except zipfile.BadZipFile as exc:
        raise ValueError('Файл не является моделью SMPL-X NPZ.') from exc


def unpack_model(path):
    """Архив загрузки SMPL-X (models_smplx_v1_1.zip) → на месте path остаётся только SMPLX_NEUTRAL.npz.
    Обычный .npz (тоже zip, но с массивами .npy) не трогаем. Возвращает True, если файл извлечён."""
    path = Path(path)
    try:
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            if any(name.endswith('.npy') for name in names):
                return False
            member = next((item for item in archive.infolist() if Path(item.filename).name == 'SMPLX_NEUTRAL.npz'), None)
            if member is None:
                raise ValueError('В архиве нет SMPLX_NEUTRAL.npz.')
            if member.file_size > 1024**3:
                raise ValueError('Файл модели слишком большой.')
            part = path.with_name(path.name + '.part')
            with archive.open(member) as source, part.open('wb') as output:
                shutil.copyfileobj(source, output, 1024 * 1024)
    except zipfile.BadZipFile as exc:
        raise ValueError('Файл не является моделью SMPL-X NPZ.') from exc
    try:
        validate_model(part)
    except ValueError:
        part.unlink(missing_ok=True)
        raise
    part.replace(path)
    return True


def sync_model(cfg, model):
    """Use the user's chosen model everywhere, including GVHMR's fixed model path."""
    if not model or not cfg.get('gvhmr_dir'):
        return
    validate_model(model)
    destination = str(cfg['gvhmr_dir']).rstrip('/') + '/inputs/checkpoints/body_models/smplx/SMPLX_NEUTRAL.npz'
    if cfg.get('gvhmr_wsl'):
        prefix = wsl_prefix(cfg)
        subprocess.run(prefix + ['mkdir', '-p', destination.rsplit('/', 1)[0]], check=True, timeout=30)
        subprocess.run(prefix + ['cp', '--', linux_path(model, cfg), destination], check=True, timeout=180)
    else:
        dst = Path(destination)
        dst.parent.mkdir(parents=True, exist_ok=True)
        if Path(model).resolve() != dst.resolve():
            shutil.copy2(model, dst)


def setup(log=print):
    from core import components, settings
    if sys.platform == 'darwin':
        raise RuntimeError('Локальный GVHMR требует NVIDIA. На Mac выберите GVHMR · Colab.')
    if not components.gpu_info().get('cuda'):
        raise RuntimeError('Не найдена NVIDIA. Установите драйвер NVIDIA, перезапустите Studio и проверьте «Модели и инструменты».')
    cfg = settings.load()
    bootstrap = ROOT / 'scripts' / 'setup_gvhmr.py'
    if os.name == 'nt':
        names = installed_distros()
        listing = subprocess.run(['wsl.exe', '--list', '--verbose'], capture_output=True, timeout=30)
        unfinished = unfinished_distros(listing.stdout)
        if unfinished:
            log('Незавершённые дистрибутивы WSL: ' + ', '.join(unfinished) + '. Данные сохранены; автоматический выбор их пропускает.')
            if cfg.get('gvhmr_wsl') in unfinished:
                raise RuntimeError('Выбранный дистрибутив ещё Installing. Завершите его первый запуск или выберите готовый дистрибутив в настройках WSL.')
            names = [name for name in names if name not in unfinished]
            if not names:
                raise RuntimeError('Нет готового дистрибутива WSL. Завершите первый запуск Ubuntu; незавершённые дистрибутивы не удалены.')
        cfg['gvhmr_wsl'] = select_distro(cfg.get('gvhmr_wsl', ''), names)
        if not cfg['gvhmr_wsl']:
            install_wsl(log)
            raise SetupPending('Завершите установку WSL, перезагрузите ПК при запросе Windows, откройте Ubuntu и повторите установку GVHMR.')
        prefix = wsl_prefix(cfg)
        probe = probe_wsl(prefix)
        if probe.returncode:
            raise RuntimeError('Не удалось запустить WSL «' + cfg['gvhmr_wsl'] + '»: ' +
                               wsl_failure(wsl_output(probe.stderr or probe.stdout)) +
                               '\nОткройте этот дистрибутив из меню «Пуск» и завершите первый запуск.')
        log('Использую WSL: ' + cfg['gvhmr_wsl'])
        check_gpu_generation()
        if not cfg.get('gvhmr_dir'):
            require_disk(15, 'GVHMR')
        version = subprocess.run(['wsl.exe','--list','--verbose'],capture_output=True,timeout=30)
        rows = [line.replace('*', '', 1).split() for line in wsl_output(version.stdout).splitlines()]
        rows = [row for row in rows if row and row[0].casefold() == cfg['gvhmr_wsl'].casefold()]
        if not rows or rows[0][-1] != '2':
            log('Перевожу Ubuntu в WSL2…')
            subprocess.run(['wsl.exe','--set-version',cfg['gvhmr_wsl'],'2'],check=True,timeout=600)
        log('Подготавливаю системные зависимости Ubuntu в WSL…')
        # Root is used only for Ubuntu packages; inference and Python use the default user.
        root = ['wsl.exe', '--distribution', cfg['gvhmr_wsl'], '--user', 'root', '--exec']
        subprocess.run(root + APT + ['update'], check=True)
        subprocess.run(root + ['env', 'DEBIAN_FRONTEND=noninteractive'] + APT + ['install', '-y',
                               'python3', 'python3-venv', 'python3-dev', 'python3-tk', 'git', 'ffmpeg', 'build-essential', 'libgl1', 'libegl1', 'libglib2.0-0'], check=True)
        command = prefix + ['python3', linux_path(bootstrap, cfg)]
    else:
        cfg['gvhmr_wsl'] = ''
        check_gpu_generation()
        import ctypes
        libraries = True
        try:
            for library in ('libGL.so.1', 'libEGL.so.1', 'libglib-2.0.so.0'):
                ctypes.CDLL(library)
        except OSError:
            libraries = False
        if not libraries or any(not shutil.which(tool) for tool in ('ffmpeg', 'git', 'gcc')) or not any(Path('/usr/include').glob('python*/Python.h')):
            apt = shutil.which('apt-get')
            elevation = [] if os.geteuid() == 0 else [shutil.which('pkexec')]
            if not apt or (elevation and not elevation[0]):
                raise RuntimeError('Linux: для автоматической установки зависимостей нужны apt-get и pkexec. '
                                   'Установите git, ffmpeg, build-essential, python3-dev, python3-tk, libgl1, libegl1, libglib2.0-0 через пакетный менеджер ОС.')
            log('Linux: подтвердите системный запрос установки зависимостей / approve the OS package installation.')
            subprocess.run(elevation + [apt] + APT[1:] + ['update'], check=True)
            subprocess.run(elevation + [apt] + APT[1:] + ['install', '-y', 'git', 'ffmpeg', 'build-essential',
                                        'python3-venv', 'python3-dev', 'python3-tk', 'libgl1', 'libegl1', 'libglib2.0-0'], check=True)
        command = [sys.executable, str(bootstrap)]
    env = {**os.environ, 'PYTHONUTF8':'1', 'PYTHONIOENCODING':'utf-8', 'HF_HUB_DISABLE_PROGRESS_BARS':'1'}
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               encoding='utf-8', errors='replace', env=env)
    runtime = None
    write, tail = setup_log(log), []
    try:
        for line in process.stdout:
            line = line.rstrip()
            if line.startswith('MOCAPGATE_RUNTIME '):
                runtime = json.loads(line.split(' ', 1)[1])
            else:
                write(line)
                tail = (tail + [line])[-200:]
        code = process.wait()
    finally:
        process.stdout.close()
    if code or runtime is None:
        reason = failure_reason(tail)
        raise RuntimeError('Установка GVHMR не завершена' + (': ' + reason if reason else f' (код {code})') +
                           '. Повторная установка продолжит скачивание.')
    cfg.update(gvhmr_dir=runtime['dir'], gvhmr_python=runtime['python'])
    settings.save({**{key:cfg[key] for key in ('gvhmr_wsl','gvhmr_dir','gvhmr_python')}, 'backend':'gvhmr-local'})
    sync_model(cfg, components.smplx_model(cfg))
    log('Окружение и веса готовы. Добавьте SMPLX_NEUTRAL.npz, если модель ещё не загружена.')
    return 0


def install_wsl(log=print):
    if os.name != 'nt':
        raise RuntimeError('WSL нужен только на Windows.')
    import ctypes
    result = ctypes.windll.shell32.ShellExecuteW(None, 'runas', 'wsl.exe',
        '--install -d Ubuntu --no-launch', None, 1)
    if result <= 32:
        raise RuntimeError('Windows не запустил установку WSL: подтвердите запрос администратора.')
    log('Открыта установка WSL в Windows. Дождитесь её завершения, перезагрузите ПК, '
        'затем нажмите «Установить GVHMR».')
    return 0
