"""Preflight: read-only checks of this computer before installing MoCapGate components.

Pure stdlib (Studio's embedded Python has no third-party packages). Nothing here installs,
repairs or changes system settings: every check only reads state and returns advice.

run(cfg=None, network=True, timeout=6) -> {
    "platform": {...},
    "checks": [{"id", "level": ok|warn|fail|info, "title": {ru,en}, "detail": {ru,en},
                "fix": {"kind": action|command|link|tip, "value", "label": {ru,en}} | None,
                "blocks": [component ids: gemx, gvhmr, blender, ffmpeg, mediapipe, smplx, all]}],
    "recommend": {"models": [...], "reason": {ru,en}},
}
Fix actions (kind "action") name Studio operations: "settings", "wslconfig", "wsl", "ffmpeg", "blender".
"""
from __future__ import annotations

import importlib
import os
import platform
import re
import shutil
import socket
import ssl
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

GB = 1024 ** 3
COLAB_URL = 'https://colab.research.google.com/'
NVIDIA_DRIVERS = 'https://www.nvidia.com/Download/index.aspx'
MIN_BUILD_OK, MIN_BUILD = 19044, 19041
DRIVER_MIN, DRIVER_OK = 525, 535
DISK_BASE, DISK_GEMX, DISK_GEMX_MAC, DISK_GVHMR = 5, 30, 14, 15
WSL_MEMORY_GEMX = 12
LONG_PATHS_COMMAND = ('New-ItemProperty -Path "HKLM:\\SYSTEM\\CurrentControlSet\\Control\\FileSystem" '
                      '-Name "LongPathsEnabled" -Value 1 -PropertyType DWORD -Force')
SYNC_MARKERS = (('onedrive', 'OneDrive'), ('dropbox', 'Dropbox'), ('icloud', 'iCloud'), ('mobile documents', 'iCloud'),
                ('google drive', 'Google Drive'), ('googledrive', 'Google Drive'), ('my drive', 'Google Drive'),
                ('yandexdisk', 'Yandex Disk'), ('yandex.disk', 'Yandex Disk'), ('megasync', 'MEGA'), ('mega', 'MEGA'))
EXACT_SYNC_FOLDERS = ('mobile documents', 'my drive', 'mega', 'megasync')
LOCAL = ('gemx', 'gvhmr')
NO_DISTRO = ('wsl_e_default_distro_not_found', 'no installed distributions', 'нет установленных дистрибутивов')
DOWNLOADS = ['gemx', 'gvhmr', 'ffmpeg', 'blender', 'mediapipe', 'smplx']
HOSTS = [
    ('github.com', 'https://github.com/', ['gemx', 'gvhmr', 'ffmpeg']),
    ('objects.githubusercontent.com', 'https://objects.githubusercontent.com/', ['gemx', 'gvhmr', 'ffmpeg']),
    ('media.githubusercontent.com', 'https://media.githubusercontent.com/', ['gemx']),
    ('huggingface.co', 'https://huggingface.co/', ['gemx', 'gvhmr']),
    ('cdn-lfs-us-1.hf.co', 'https://cdn-lfs-us-1.hf.co/', ['gemx', 'gvhmr']),
    ('cas-bridge.xethub.hf.co', 'https://cas-bridge.xethub.hf.co/', ['gemx', 'gvhmr']),
    ('pypi.org', 'https://pypi.org/simple/pip/', ['gemx', 'gvhmr', 'ffmpeg', 'mediapipe', 'smplx']),
    ('files.pythonhosted.org', 'https://files.pythonhosted.org/', ['gemx', 'gvhmr', 'ffmpeg', 'mediapipe', 'smplx']),
    ('download.pytorch.org', 'https://download.pytorch.org/whl/', ['gemx', 'gvhmr', 'smplx']),
    ('download.blender.org', 'https://download.blender.org/release/', ['blender']),
    ('storage.googleapis.com', 'https://storage.googleapis.com/mediapipe-models/', ['mediapipe']),
    ('download.openmmlab.com', 'https://download.openmmlab.com/', ['gemx']),
]
FFPROBE_HOSTS = {'Windows': ('www.gyan.dev', 'https://www.gyan.dev/ffmpeg/builds/', ['ffmpeg']),
                 'Darwin': ('www.osxexperts.net', 'https://www.osxexperts.net/', ['ffmpeg']),
                 'Linux': ('api.github.com', 'https://api.github.com/', ['ffmpeg'])}


# ------------------------------------------------------------------ small helpers (patched in tests)

def t(ru, en):
    return {'ru': ru, 'en': en}


def fix(kind, value, ru, en, **extra):
    return {'kind': kind, 'value': value, 'label': t(ru, en), **extra}


def check(cid, level, title, detail, fix=None, blocks=(), data=None):
    item = {'id': cid, 'level': level, 'title': title, 'detail': detail, 'fix': fix, 'blocks': list(blocks)}
    if data:
        item['data'] = data
    return item


def _system():
    return platform.system()


def _machine():
    return platform.machine()


def _windows_build():
    try:
        return sys.getwindowsversion().build
    except AttributeError:
        parts = platform.version().split('.')
        return int(parts[2]) if len(parts) >= 3 and parts[2].isdigit() else 0


def _mac_version():
    return platform.mac_ver()[0]


def _winreg():
    try:
        return importlib.import_module('winreg')
    except ImportError:
        return None


def _env(name, default=''):
    return os.environ.get(name) or default


def _decode(raw):
    if raw is None:
        return ''
    from core.gvhmr_environment import wsl_output
    return wsl_output(raw)


def _cmd(args, timeout=10):
    """Run a read-only command: {'code': int|None, 'out': str, 'timeout': bool, 'missing': bool}."""
    kwargs = {'capture_output': True, 'timeout': timeout}
    flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    if flags:
        kwargs['creationflags'] = flags
    try:
        result = subprocess.run(args, **kwargs)
    except subprocess.TimeoutExpired:
        return {'code': None, 'out': '', 'timeout': True, 'missing': False}
    except (OSError, ValueError) as exc:
        return {'code': None, 'out': str(exc), 'timeout': False, 'missing': True}
    out = _decode(result.stdout) + ('\n' + _decode(result.stderr) if result.stderr else '')
    return {'code': result.returncode, 'out': out.strip(), 'timeout': False, 'missing': False}


def _reg_value(root, key, name):
    reg = _winreg()
    if reg is None:
        return None
    try:
        handle = reg.OpenKey(getattr(reg, root), key)
    except OSError:
        return None
    try:
        return reg.QueryValueEx(handle, name)[0]
    except OSError:
        return None
    finally:
        try:
            reg.CloseKey(handle)
        except Exception:
            pass


def _reg_exists(root, key):
    reg = _winreg()
    if reg is None:
        return False
    try:
        reg.CloseKey(reg.OpenKey(getattr(reg, root), key))
        return True
    except OSError:
        return False


def _ram_bytes():
    system = _system()
    if system == 'Windows':
        import ctypes

        class MemoryStatus(ctypes.Structure):
            _fields_ = [('dwLength', ctypes.c_ulong), ('dwMemoryLoad', ctypes.c_ulong),
                        ('ullTotalPhys', ctypes.c_ulonglong), ('ullAvailPhys', ctypes.c_ulonglong),
                        ('ullTotalPageFile', ctypes.c_ulonglong), ('ullAvailPageFile', ctypes.c_ulonglong),
                        ('ullTotalVirtual', ctypes.c_ulonglong), ('ullAvailVirtual', ctypes.c_ulonglong),
                        ('ullAvailExtendedVirtual', ctypes.c_ulonglong)]
        status = MemoryStatus()
        status.dwLength = ctypes.sizeof(MemoryStatus)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return None
        return int(status.ullTotalPhys)
    if system == 'Darwin':
        result = _cmd(['sysctl', '-n', 'hw.memsize'], 5)
        return int(result['out'].split()[0]) if result['code'] == 0 and result['out'] else None
    with open('/proc/meminfo', encoding='ascii', errors='replace') as stream:
        for line in stream:
            if line.startswith('MemTotal:'):
                return int(line.split()[1]) * 1024
    return None


def _existing(path):
    path = Path(path)
    while not path.exists() and path.parent != path:
        path = path.parent
    return path


def _disk_free(path):
    return shutil.disk_usage(str(_existing(path))).free


def _gb(value):
    return round(value / GB, 1)


def _apple_silicon():
    if _system() != 'Darwin':
        return False
    if _machine() == 'arm64':
        return True
    result = _cmd(['sysctl', '-n', 'hw.optional.arm64'], 5)  # x86 Python under Rosetta
    return result['code'] == 0 and result['out'].strip() == '1'


def _runtime_dir():
    """Where large components live: WSL disks under %LOCALAPPDATA% on Windows, ~/.cache/mocapgate elsewhere."""
    if _system() == 'Windows':
        return Path(_env('LOCALAPPDATA') or Path.home() / 'AppData' / 'Local')
    from core.components import HOME
    return HOME


def _library(cfg):
    from core import settings
    return settings.library(cfg)


# ------------------------------------------------------------------ checks

def check_os(ctx):
    system, machine = ctx['system'], ctx['machine'].lower()
    out = []
    is64 = sys.maxsize > 2 ** 32 and machine in ('amd64', 'x86_64', 'arm64', 'aarch64')
    if system == 'Windows' and _env('PROCESSOR_ARCHITEW6432'):
        is64 = True  # 32-bit process on 64-bit Windows
    if not is64:
        out.append(check('os.arch', 'fail', t('Нужна 64-битная система', '64-bit system required'),
                         t(f'Архитектура {ctx["machine"]} не поддерживается.', f'Architecture {ctx["machine"]} is not supported.'),
                         blocks=['all']))
    elif system == 'Windows' and machine in ('arm64', 'aarch64'):
        out.append(check('os.arch', 'fail', t('Windows на ARM64', 'Windows on ARM64'),
                         t('Локальные GEM-X и GVHMR требуют x64 и NVIDIA CUDA. Используйте GVHMR · Colab.',
                           'Local GEM-X and GVHMR need x64 and NVIDIA CUDA. Use GVHMR · Colab.'),
                         fix('link', COLAB_URL, 'Открыть Colab', 'Open Colab'), blocks=list(LOCAL)))
    else:
        out.append(check('os.arch', 'ok', t('64-битная система', '64-bit system'),
                         t(f'{system} {ctx["machine"]}', f'{system} {ctx["machine"]}')))
    if system == 'Windows':
        build = ctx.get('build') or 0
        if build >= MIN_BUILD_OK:
            level, blocks = 'ok', []
            detail = t(f'Сборка Windows {build}: WSL2 с GPU поддерживается.', f'Windows build {build}: WSL2 GPU is supported.')
        elif build >= MIN_BUILD:
            level, blocks = 'warn', []
            detail = t(f'Сборка {build} старее Windows 10 21H2 (19044). WSL2 с CUDA может не работать — обновите Windows.',
                       f'Build {build} is older than Windows 10 21H2 (19044). WSL2 CUDA may not work — update Windows.')
        else:
            level, blocks = 'fail', list(LOCAL)
            detail = t(f'Сборка {build} не поддерживает WSL2 с GPU. Обновите Windows до 10 21H2 или 11.',
                       f'Build {build} does not support WSL2 GPU. Update to Windows 10 21H2 or Windows 11.')
        out.append(check('os.windows_build', level, t('Версия Windows', 'Windows version'), detail,
                         fix('command', 'ms-settings:windowsupdate', 'Открыть Центр обновления', 'Open Windows Update')
                         if level != 'ok' else None, blocks))
    elif system == 'Darwin':
        version = ctx.get('mac_version') or '?'
        if ctx.get('apple_silicon'):
            out.append(check('os.macos', 'ok', t('macOS на Apple Silicon', 'macOS on Apple Silicon'),
                             t(f'macOS {version}: GEM-X работает локально (ONNX / CoreML).',
                               f'macOS {version}: GEM-X runs locally (ONNX / CoreML).')))
        else:
            out.append(check('os.macos', 'info', t('macOS на Intel', 'macOS on Intel'),
                             t(f'macOS {version} на Intel: локальный GEM-X будет очень медленным или не запустится; '
                               'GVHMR · Colab — надёжный вариант.',
                               f'macOS {version} on Intel: local GEM-X will be very slow or may not run; '
                               'GVHMR · Colab is the reliable option.'),
                             fix('link', COLAB_URL, 'Открыть Colab', 'Open Colab')))
    return out


def check_ram(ctx):
    total = ctx.get('ram')
    if not total:
        return [check('ram', 'warn', t('Оперативная память', 'Memory (RAM)'),
                      t('Не удалось определить объём памяти.', 'Could not determine the amount of memory.'))]
    gb = _gb(total)
    if gb < 7.5:  # «8 ГБ» модули показывают ~7.8 ГБ
        return [check('ram', 'fail', t('Мало оперативной памяти', 'Not enough memory'),
                      t(f'{gb} ГБ: для GEM-X и GVHMR нужно минимум 8 ГБ (лучше 16+). Используйте GVHMR · Colab.',
                        f'{gb} GB: GEM-X and GVHMR need at least 8 GB (16+ recommended). Use GVHMR · Colab.'),
                      fix('link', COLAB_URL, 'Открыть Colab', 'Open Colab'), list(LOCAL), {'gb': gb})]
    if gb < 15:
        return [check('ram', 'warn', t('Оперативная память', 'Memory (RAM)'),
                      t(f'{gb} ГБ: локальная обработка возможна, но длинные видео могут не поместиться. Рекомендуется 16 ГБ.',
                        f'{gb} GB: local processing works but long videos may not fit. 16 GB is recommended.'),
                      fix('tip', '', 'Закройте браузер и другие тяжёлые программы на время обработки.',
                          'Close browsers and other heavy apps while processing.'), data={'gb': gb})]
    return [check('ram', 'ok', t('Оперативная память', 'Memory (RAM)'), t(f'{gb} ГБ', f'{gb} GB'), data={'gb': gb})]


def check_disk(ctx):
    out = []
    cfg = ctx['cfg']
    library = ctx['library']
    try:
        free = _disk_free(library)
        level = 'ok' if free >= DISK_BASE * GB else 'fail'
        out.append(check('disk.library', level, t('Место для дублей', 'Space for takes'),
                         t(f'Свободно {_gb(free)} ГБ на диске с папкой дублей ({_existing(library).anchor or library}). '
                           f'Нужно не меньше {DISK_BASE} ГБ.',
                           f'{_gb(free)} GB free on the takes drive ({_existing(library).anchor or library}). '
                           f'At least {DISK_BASE} GB is needed.'),
                         fix('action', 'settings', 'Выбрать другую папку', 'Choose another folder') if level != 'ok' else None,
                         ['all'] if level != 'ok' else [], {'free_gb': _gb(free)}))
    except Exception as exc:
        out.append(_error('disk.library', exc))
    runtime = ctx['runtime']
    free = _disk_free(runtime)
    need = {'gemx': DISK_GEMX_MAC if ctx['system'] == 'Darwin' else DISK_GEMX, 'gvhmr': DISK_GVHMR}
    installed = {'gemx': bool(cfg.get('gemx_dir')), 'gvhmr': bool(cfg.get('gvhmr_dir'))}
    if free < DISK_BASE * GB:
        blocks = ['all']
    else:
        blocks = [c for c in LOCAL if not installed[c] and free < need[c] * GB]
    where = _existing(runtime).anchor or str(runtime)
    if blocks:
        names = ', '.join('GEM-X' if b == 'gemx' else 'GVHMR' if b == 'gvhmr' else b for b in blocks)
        detail = t(f'Свободно {_gb(free)} ГБ на диске {where}, где ставятся модели и WSL. Не хватает для: {names} '
                   f'(GEM-X ~{need["gemx"]} ГБ, GVHMR ~{need["gvhmr"]} ГБ, основа {DISK_BASE} ГБ).',
                   f'{_gb(free)} GB free on {where}, where models and WSL are installed. Not enough for: {names} '
                   f'(GEM-X ~{need["gemx"]} GB, GVHMR ~{need["gvhmr"]} GB, base {DISK_BASE} GB).')
        out.append(check('disk.runtime', 'fail', t('Место для моделей', 'Space for models'), detail,
                         fix('tip', '', 'Освободите место на этом диске (Корзина, Загрузки, старые игры).',
                             'Free up space on this drive (Recycle Bin, Downloads, old games).'),
                         blocks, {'free_gb': _gb(free)}))
    else:
        out.append(check('disk.runtime', 'ok', t('Место для моделей', 'Space for models'),
                         t(f'Свободно {_gb(free)} ГБ на диске {where}.', f'{_gb(free)} GB free on {where}.'),
                         data={'free_gb': _gb(free)}))
    return out


def sync_service(path):
    """Name of a cloud-sync service whose folder contains path, or ''."""
    text = str(path).replace('\\', '/')
    lowered = text.casefold()
    for env in ('OneDrive', 'OneDriveConsumer', 'OneDriveCommercial'):
        root = _env(env).replace('\\', '/').rstrip('/').casefold()
        if root and (lowered == root or lowered.startswith(root + '/')):
            return 'OneDrive'
    for part in (p.casefold() for p in text.split('/') if p):
        for marker, name in SYNC_MARKERS:
            if (part == marker) if marker in EXACT_SYNC_FOLDERS else part.startswith(marker):
                return name
    if _system() == 'Darwin':
        home = str(Path.home()).replace('\\', '/').casefold()
        clouddocs = Path.home() / 'Library' / 'Mobile Documents' / 'com~apple~CloudDocs'
        for folder in ('Documents', 'Desktop'):
            base = home + '/' + folder.casefold()
            if (lowered == base or lowered.startswith(base + '/')) and (clouddocs / folder).is_dir():
                return 'iCloud'
    return ''


def check_library(ctx):
    out = []
    library = Path(ctx['library'])
    target = _existing(library)
    try:
        with tempfile.NamedTemporaryFile(dir=str(target), prefix='.mocapgate-preflight-'):
            pass
        out.append(check('library.writable', 'ok', t('Папка дублей доступна', 'Takes folder is writable'),
                         t(str(library), str(library))))
    except Exception as exc:
        out.append(check('library.writable', 'fail', t('Нет записи в папку дублей', 'Takes folder is not writable'),
                         t(f'{library}: {exc}. Выберите другую папку или проверьте антивирус (защита папок).',
                           f'{library}: {exc}. Choose another folder or check antivirus folder protection.'),
                         fix('action', 'settings', 'Выбрать другую папку', 'Choose another folder'), ['all']))
    service = sync_service(library)
    if service:
        out.append(check('library.sync', 'warn', t('Папка дублей синхронизируется', 'Takes folder is cloud-synced'),
                         t(f'{library} находится в {service}. Синхронизация блокирует и выгружает большие файлы — '
                           'обработка может падать. Выберите папку вне облака.',
                           f'{library} is inside {service}. Sync locks and offloads large files, which breaks processing. '
                           'Choose a folder outside the cloud.'),
                         fix('action', 'settings', 'Выбрать другую папку', 'Choose another folder'), data={'service': service}))
    if ctx['system'] == 'Windows':
        length = len(str(library))
        if length > 120:
            out.append(check('library.path_length', 'warn', t('Длинный путь к папке дублей', 'Long takes folder path'),
                             t(f'Путь из {length} символов: файлы внутри дубля могут превысить предел Windows 260 символов.',
                               f'The path is {length} characters: files inside a take may exceed the Windows 260-character limit.'),
                             fix('action', 'settings', 'Выбрать короткий путь, например C:\\MoCap',
                                 'Choose a short path such as C:\\MoCap')))
        enabled = _reg_value('HKEY_LOCAL_MACHINE', r'SYSTEM\CurrentControlSet\Control\FileSystem', 'LongPathsEnabled')
        if enabled == 1:
            out.append(check('windows.long_paths', 'ok', t('Длинные пути включены', 'Long paths enabled'),
                             t('LongPathsEnabled = 1', 'LongPathsEnabled = 1')))
        else:
            out.append(check('windows.long_paths', 'warn', t('Длинные пути выключены', 'Long paths disabled'),
                             t('Windows ограничивает пути 260 символами; глубокие папки моделей могут не распаковаться.',
                               'Windows limits paths to 260 characters; deep model folders may fail to unpack.'),
                             fix('command', LONG_PATHS_COMMAND, 'Выполнить в PowerShell от администратора',
                                 'Run in PowerShell as administrator')))
    return out


def check_home(ctx):
    home = str(Path.home())
    if home.isascii():
        return []
    return [check('home.non_ascii', 'info', t('Не-ASCII символы в профиле', 'Non-ASCII characters in profile path'),
                  t(f'{home}: поддерживается, но если сторонний инструмент не найдёт файл, выберите папку дублей '
                    'с латинскими буквами.',
                    f'{home}: supported, but if a third-party tool cannot find a file, choose a takes folder '
                    'with Latin characters.'),
                  fix('action', 'settings', 'Выбрать папку', 'Choose folder'))]


def _probe_url(url, timeout):
    """One HEAD request: reachable host → kind 'ok'/'http'; otherwise ssl/dns/timeout/refused/error."""
    from core.install_util import AGENT
    request = urllib.request.Request(url, method='HEAD', headers={'User-Agent': AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return {'kind': 'ok', 'status': response.status, 'error': ''}
    except urllib.error.HTTPError as exc:
        exc.close()
        return {'kind': 'http', 'status': exc.code, 'error': str(exc)}
    except urllib.error.URLError as exc:
        reason = exc.reason
        if isinstance(reason, ssl.SSLError) or 'CERTIFICATE_VERIFY_FAILED' in str(reason):
            return {'kind': 'ssl', 'status': None, 'error': str(reason)}
        if isinstance(reason, socket.gaierror):
            return {'kind': 'dns', 'status': None, 'error': str(reason)}
        if isinstance(reason, (socket.timeout, TimeoutError)):
            return {'kind': 'timeout', 'status': None, 'error': str(reason)}
        if isinstance(reason, ConnectionRefusedError):
            return {'kind': 'refused', 'status': None, 'error': str(reason)}
        return {'kind': 'error', 'status': None, 'error': str(reason)}
    except ssl.SSLError as exc:
        return {'kind': 'ssl', 'status': None, 'error': str(exc)}
    except (socket.timeout, TimeoutError) as exc:
        return {'kind': 'timeout', 'status': None, 'error': str(exc)}
    except Exception as exc:
        return {'kind': 'error', 'status': None, 'error': str(exc)}


def proxies():
    found = {}
    for name in ('HTTPS_PROXY', 'HTTP_PROXY', 'ALL_PROXY', 'https_proxy', 'http_proxy', 'all_proxy'):
        if os.environ.get(name):
            found[name.upper()] = os.environ[name]
    if _system() == 'Windows':
        key = r'Software\Microsoft\Windows\CurrentVersion\Internet Settings'
        if _reg_value('HKEY_CURRENT_USER', key, 'ProxyEnable') == 1:
            found['WINDOWS'] = _reg_value('HKEY_CURRENT_USER', key, 'ProxyServer') or '?'
        script = _reg_value('HKEY_CURRENT_USER', key, 'AutoConfigURL')
        if script:
            found['PAC'] = script
    return found


def _strip_credentials(value):
    return re.sub(r'//[^/@\s]+@', '//***@', str(value))


def check_proxy(ctx):
    found = proxies()
    if not found:
        return []
    listing = ', '.join(f'{k}={_strip_credentials(v)}' for k, v in sorted(found.items()))
    return [check('network.proxy', 'info', t('Используется прокси', 'Proxy in use'),
                  t(f'{listing}. Если загрузки не идут, проверьте, что прокси пропускает перечисленные хосты.',
                    f'{listing}. If downloads fail, make sure the proxy allows the listed hosts.'))]


def check_network(ctx):
    timeout = ctx['timeout']
    hosts = list(HOSTS)
    extra = FFPROBE_HOSTS.get(ctx['system'])
    if extra:
        hosts.append(extra)
    results = {}

    def worker(name, url):
        results[name] = _probe_url(url, timeout)

    threads = [threading.Thread(target=worker, args=(name, url), daemon=True) for name, url, _ in hosts]
    for thread in threads:
        thread.start()
    deadline = time.monotonic() + timeout + 2
    for thread in threads:
        thread.join(max(0.0, deadline - time.monotonic()))
    unreachable, ssl_hosts, limited, blocks = [], [], [], set()
    for name, _, components in hosts:
        result = results.get(name) or {'kind': 'timeout', 'status': None, 'error': 'no answer'}
        if result['kind'] in ('ok', 'http'):
            if result['status'] == 429:
                limited.append(name)
            continue
        unreachable.append(name)
        blocks.update(components)
        if result['kind'] == 'ssl':
            ssl_hosts.append(name)
    data = {name: results.get(name, {'kind': 'timeout'}) for name, _, _ in hosts}
    out = []
    if len(unreachable) == len(hosts):
        out.append(check('network', 'fail', t('Нет доступа в интернет', 'No internet access'),
                         t('Ни один сервер загрузки не ответил. Компоненты не скачаются.',
                           'No download server answered. Components cannot be downloaded.'),
                         fix('tip', '', 'Проверьте подключение, VPN и прокси, затем повторите проверку.',
                             'Check the connection, VPN and proxy, then run the check again.'), ['all'], data))
    elif unreachable:
        listing = ', '.join(unreachable)
        out.append(check('network', 'warn', t('Часть серверов недоступна', 'Some servers are unreachable'),
                         t(f'Не отвечают: {listing}. Загрузки с них не пройдут.', f'Not reachable: {listing}. Downloads from them will fail.'),
                         fix('tip', '', 'Попробуйте другую сеть или VPN; проверьте фаервол и прокси.',
                             'Try another network or VPN; check the firewall and proxy.'),
                         sorted(blocks), data))
    else:
        out.append(check('network', 'ok', t('Серверы загрузки доступны', 'Download servers reachable'),
                         t(f'Отвечают все {len(hosts)} серверов.', f'All {len(hosts)} servers answer.'), data=data))
    if ssl_hosts:
        out.append(check('network.ssl', 'warn', t('HTTPS перехватывается', 'HTTPS is intercepted'),
                         t(f'Сертификат не прошёл проверку для: {", ".join(ssl_hosts)}. Обычно это проверка HTTPS в антивирусе '
                           'или корпоративный прокси.',
                           f'Certificate verification failed for: {", ".join(ssl_hosts)}. This is usually antivirus HTTPS '
                           'scanning or a corporate proxy.'),
                         fix('tip', '', 'Отключите проверку HTTPS в антивирусе для MoCapGate или используйте другую сеть.',
                             'Disable antivirus HTTPS scanning for MoCapGate or use another network.')))
    if limited:
        out.append(check('network.rate_limit', 'warn', t('Сервер ограничил запросы', 'Server rate limit'),
                         t(f'HTTP 429 от: {", ".join(limited)}. Подождите несколько минут.',
                           f'HTTP 429 from: {", ".join(limited)}. Wait a few minutes.')))
    return out


def nvidia_smi():
    smi = shutil.which('nvidia-smi')
    if not smi and _system() == 'Windows':
        for candidate in (os.path.join(_env('SystemRoot', 'C:\\Windows'), 'System32', 'nvidia-smi.exe'),
                          os.path.join(_env('ProgramFiles', 'C:\\Program Files'), 'NVIDIA Corporation', 'NVSMI', 'nvidia-smi.exe')):
            if os.path.isfile(candidate):
                return candidate
    return smi


def parse_gpus(text):
    """Rows of `nvidia-smi --query-gpu=name,driver_version,memory.total[,compute_cap] --format=csv,noheader`."""
    gpus = []
    for line in text.splitlines():
        cells = [c.strip() for c in line.split(',')]
        if len(cells) < 3 or not re.match(r'\d', cells[1]):
            continue
        memory = re.match(r'([\d.]+)', cells[2])
        cap = None
        if len(cells) > 3:
            found = re.match(r'(\d+)\.(\d+)', cells[3])
            cap = (int(found.group(1)), int(found.group(2))) if found else None
        gpus.append({'name': cells[0], 'driver': cells[1], 'vram_gb': round(float(memory.group(1)) / 1024, 1) if memory else 0.0,
                     'cap': cap})
    return gpus


def check_gpu(ctx):
    system = ctx['system']
    if system == 'Darwin':
        chip = _cmd(['sysctl', '-n', 'machdep.cpu.brand_string'], 5)['out'] or ctx['machine']
        ctx['gpu'] = {'kind': 'apple' if ctx.get('apple_silicon') else 'cpu', 'name': chip}
        return [check('gpu.apple', 'info', t('Графика Mac', 'Mac graphics'),
                      t(f'{chip}. CUDA на Mac нет: GVHMR — через Colab' + (', GEM-X — локально.' if ctx.get('apple_silicon') else '.'),
                        f'{chip}. Macs have no CUDA: GVHMR runs in Colab' + (', GEM-X runs locally.' if ctx.get('apple_silicon') else '.')))]
    smi = nvidia_smi()
    no_nvidia = check('gpu.nvidia', 'fail', t('Нет видеокарты NVIDIA', 'No NVIDIA GPU'),
                      t('Локальные GEM-X и GVHMR требуют NVIDIA с CUDA и драйвером. Обрабатывайте видео в GVHMR · Colab '
                        'или установите драйвер NVIDIA, если карта есть.',
                        'Local GEM-X and GVHMR need an NVIDIA GPU with CUDA drivers. Process videos with GVHMR · Colab '
                        'or install the NVIDIA driver if you have such a card.'),
                      fix('link', COLAB_URL, 'Открыть Colab', 'Open Colab'), list(LOCAL))
    ctx['gpu'] = {'kind': 'cpu'}
    if not smi:
        return [no_nvidia]
    query = '--query-gpu=name,driver_version,memory.total,compute_cap'
    result = _cmd([smi, query, '--format=csv,noheader'], 10)
    gpus = parse_gpus(result['out']) if result['code'] == 0 else []
    if not gpus and not result['timeout']:  # old drivers do not know compute_cap
        result = _cmd([smi, '--query-gpu=name,driver_version,memory.total', '--format=csv,noheader'], 10)
        gpus = parse_gpus(result['out']) if result['code'] == 0 else []
    if not gpus:
        detail = result['out'][-300:] or ('timeout' if result['timeout'] else '')
        return [check('gpu.nvidia', 'fail', t('Драйвер NVIDIA не отвечает', 'NVIDIA driver does not respond'),
                      t(f'nvidia-smi не вернул данные: {detail}. Переустановите драйвер NVIDIA и перезагрузите ПК.',
                        f'nvidia-smi returned no data: {detail}. Reinstall the NVIDIA driver and reboot.'),
                      fix('link', NVIDIA_DRIVERS, 'Скачать драйвер NVIDIA', 'Download NVIDIA driver'), list(LOCAL))]
    gpu = max(gpus, key=lambda g: g['vram_gb'])
    ctx['gpu'] = {'kind': 'nvidia', **gpu}
    out = [check('gpu.nvidia', 'ok', t('Видеокарта NVIDIA', 'NVIDIA GPU'),
                 t(f'{gpu["name"]}, {gpu["vram_gb"]} ГБ, драйвер {gpu["driver"]}',
                   f'{gpu["name"]}, {gpu["vram_gb"]} GB, driver {gpu["driver"]}'), data=dict(gpu))]
    try:
        major = int(gpu['driver'].split('.')[0])
    except ValueError:
        major = 0
    driver_fix = fix('link', NVIDIA_DRIVERS, 'Скачать драйвер NVIDIA', 'Download NVIDIA driver')
    if major < DRIVER_MIN:
        out.append(check('gpu.driver', 'fail', t('Старый драйвер NVIDIA', 'Outdated NVIDIA driver'),
                         t(f'Драйвер {gpu["driver"]}: для CUDA 12 нужен {DRIVER_OK} или новее.',
                           f'Driver {gpu["driver"]}: CUDA 12 needs {DRIVER_OK} or newer.'), driver_fix, list(LOCAL)))
    elif major < DRIVER_OK:
        out.append(check('gpu.driver', 'warn', t('Драйвер NVIDIA стоит обновить', 'Update the NVIDIA driver'),
                         t(f'Драйвер {gpu["driver"]}: рекомендуется {DRIVER_OK}+ для CUDA 12 (GEM-X).',
                           f'Driver {gpu["driver"]}: {DRIVER_OK}+ is recommended for CUDA 12 (GEM-X).'), driver_fix))
    else:
        out.append(check('gpu.driver', 'ok', t('Драйвер NVIDIA', 'NVIDIA driver'), t(gpu['driver'], gpu['driver'])))
    vram = gpu['vram_gb']
    if vram < 5.5:
        out.append(check('gpu.vram', 'fail', t('Мало видеопамяти', 'Not enough VRAM'),
                         t(f'{vram} ГБ: GEM-X нужно 8 ГБ, GVHMR — 6 ГБ. Используйте GVHMR · Colab.',
                           f'{vram} GB: GEM-X needs 8 GB and GVHMR 6 GB. Use GVHMR · Colab.'),
                         fix('link', COLAB_URL, 'Открыть Colab', 'Open Colab'), list(LOCAL)))
    elif vram < 7.5:
        out.append(check('gpu.vram', 'warn', t('Видеопамяти впритык', 'VRAM is tight'),
                         t(f'{vram} ГБ: GVHMR работает, для GEM-X рекомендуется 8 ГБ — берите короткие видео.',
                           f'{vram} GB: GVHMR works; GEM-X recommends 8 GB — use short videos.')))
    else:
        out.append(check('gpu.vram', 'ok', t('Видеопамять', 'VRAM'), t(f'{vram} ГБ', f'{vram} GB')))
    cap = gpu.get('cap')
    if cap and cap[0] >= 12:
        out.append(check('gpu.compute_cap', 'fail', t('GVHMR не поддерживает эту видеокарту', 'GVHMR does not support this GPU'),
                         t(f'Compute capability {cap[0]}.{cap[1]} (RTX 50-серия): GVHMR собран на PyTorch 2.3 / CUDA 12.1 без '
                           'поддержки sm_120. Используйте GEM-X или GVHMR · Colab.',
                           f'Compute capability {cap[0]}.{cap[1]} (RTX 50 series): GVHMR is built on PyTorch 2.3 / CUDA 12.1 '
                           'without sm_120 support. Use GEM-X or GVHMR · Colab.'),
                         fix('tip', '', 'Выберите GEM-X в настройках обработки.', 'Choose GEM-X in processing settings.'),
                         ['gvhmr'], {'cap': f'{cap[0]}.{cap[1]}'}))
    elif cap:
        out.append(check('gpu.compute_cap', 'ok', t('Архитектура GPU', 'GPU architecture'),
                         t(f'Compute capability {cap[0]}.{cap[1]}', f'Compute capability {cap[0]}.{cap[1]}')))
    return out


def parse_wsl_list(text):
    """`wsl -l -v` → [{'name','state','version','default'}] (localized headers are skipped)."""
    rows = []
    for line in _decode(text).splitlines():
        default = line.strip().startswith('*')
        row = line.strip().lstrip('*').split()
        if len(row) >= 3 and row[-1].isdigit():
            rows.append({'name': row[0], 'state': ' '.join(row[1:-1]), 'version': int(row[-1]), 'default': default})
    return rows


def default_wsl_version(text):
    found = re.search(r'^(?=.*(?:default|умолчани|standard))(?=.*(?:version|верси)).*?[:：]\s*([12])\s*$',
                      _decode(text), re.IGNORECASE | re.MULTILINE)
    return int(found.group(1)) if found else None


def parse_wslconfig_memory(text):
    """[wsl2] memory=… in GB, or None."""
    section = ''
    for line in (text or '').splitlines():
        stripped = line.strip()
        if stripped.startswith('[') and stripped.endswith(']'):
            section = stripped[1:-1].strip().casefold()
        elif section == 'wsl2' and '=' in stripped and not stripped.startswith(('#', ';')):
            key, value = stripped.split('=', 1)
            if key.strip().casefold() == 'memory':
                found = re.match(r'\s*([\d.]+)\s*([kmgt]?)b?', value.strip().casefold())
                if found:
                    scale = {'': 1 / GB, 'k': 1 / 1024 ** 2, 'm': 1 / 1024, 'g': 1, 't': 1024}[found.group(2)]
                    return round(float(found.group(1)) * scale, 1)
    return None


def wslconfig_text(current_text, memory_gb, swap_gb):
    """Set [wsl2] memory=XGB and swap=YGB, preserving every other line, comment and section."""
    text = current_text or ''
    newline = '\r\n' if '\r\n' in text else '\n'
    lines = text.splitlines()
    values = {'memory': f'{int(memory_gb)}GB', 'swap': f'{int(swap_gb)}GB'}
    start = next((i for i, line in enumerate(lines) if line.strip().casefold() == '[wsl2]'), None)
    if start is None:
        while lines and not lines[-1].strip():
            lines.pop()
        if lines:
            lines.append('')
        lines += ['[wsl2]'] + [f'{k}={v}' for k, v in values.items()]
        return newline.join(lines) + newline
    end = next((i for i in range(start + 1, len(lines)) if lines[i].strip().startswith('[')), len(lines))
    pending = dict(values)
    for i in range(start + 1, end):
        stripped = lines[i].strip()
        if '=' in stripped and not stripped.startswith(('#', ';')):
            key = stripped.split('=', 1)[0].strip().casefold()
            if key in pending:
                lines[i] = f'{key}={pending.pop(key)}'
            elif key in values:
                lines[i] = None  # duplicate key: keep only the first
    insert = end
    while insert > start + 1 and lines[insert - 1] is not None and not lines[insert - 1].strip():
        insert -= 1
    lines[insert:insert] = [f'{k}={v}' for k, v in pending.items()]
    return newline.join(line for line in lines if line is not None) + newline


def suggested_wsl_memory(ram_gb):
    return max(2, int(min(ram_gb - 4, max(WSL_MEMORY_GEMX, round(ram_gb * 0.75)))))


def check_wsl(ctx):
    if ctx['system'] != 'Windows':
        return []
    from core.gvhmr_environment import select_distro
    from core import install_help
    out = []
    wsl = shutil.which('wsl.exe') or os.path.join(_env('SystemRoot', 'C:\\Windows'), 'System32', 'wsl.exe')
    install = fix('action', 'wsl', 'Установить WSL и Ubuntu', 'Install WSL and Ubuntu')
    if not shutil.which('wsl.exe') and not os.path.isfile(wsl):
        out.append(check('wsl.present', 'fail', t('WSL не установлен', 'WSL is not installed'),
                         t('GEM-X и GVHMR на Windows работают внутри WSL2 Ubuntu.', 'GEM-X and GVHMR on Windows run inside WSL2 Ubuntu.'),
                         install, list(LOCAL)))
        out += check_virtualization(ctx)
        return out
    status = _cmd([wsl, '--status'], 20)
    listing = _cmd([wsl, '--list', '--verbose'], 20)
    if status['timeout'] or listing['timeout']:
        out.append(check('wsl.status', 'fail', t('WSL не отвечает', 'WSL does not respond'),
                         t('WSL завис. Выполните в PowerShell: wsl --shutdown, или перезагрузите компьютер.',
                           'WSL is hung. Run in PowerShell: wsl --shutdown, or reboot the computer.'),
                         fix('command', 'wsl --shutdown', 'Перезапустить WSL', 'Restart WSL'), list(LOCAL)))
        out += check_virtualization(ctx)
        return out
    rows = parse_wsl_list(listing['out']) if listing['code'] == 0 else []
    default = default_wsl_version(status['out'])
    no_distro = any(m in (status['out'] + listing['out']).casefold() for m in NO_DISTRO)
    if status['code'] and not rows and not no_distro:
        advice = install_help.advise(status['out'])
        first = advice[0] if advice else None
        pending = _reg_exists('HKEY_LOCAL_MACHINE',
                              r'SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending')
        hint_ru = (first['ru'] + ' ') if first else ''
        hint_en = (first['en'] + ' ') if first else ''
        if pending:
            hint_ru += 'Windows ждёт перезагрузки — перезагрузите ПК, чтобы включить WSL.'
            hint_en += 'Windows is waiting for a reboot — restart the PC to finish enabling WSL.'
        out.append(check('wsl.status', 'fail', t('WSL не включён', 'WSL is not enabled'),
                         t((hint_ru or 'wsl --status завершился с ошибкой. ') + ' ' + status['out'][-300:],
                           (hint_en or 'wsl --status failed. ') + ' ' + status['out'][-300:]),
                         (first or {}).get('fix') or install, list(LOCAL), {'reboot_pending': pending}))
        out += check_virtualization(ctx)
        return out
    if default == 1:
        out.append(check('wsl.default_version', 'warn', t('WSL по умолчанию версии 1', 'WSL defaults to version 1'),
                         t('Новые дистрибутивы будут WSL1 без GPU.', 'New distributions will be WSL1 without GPU access.'),
                         fix('command', 'wsl --set-default-version 2', 'Сделать WSL2 версией по умолчанию', 'Make WSL2 the default')))
    elif default == 2:
        out.append(check('wsl.default_version', 'ok', t('WSL2 по умолчанию', 'WSL2 is the default'), t('wsl --status', 'wsl --status')))
    unfinished = [r['name'] for r in rows if any(w in r['state'].casefold() for w in _installing())]
    ready = [r for r in rows if r['name'] not in unfinished]
    cfg = ctx['cfg']
    requested = cfg.get('gemx_wsl') or cfg.get('gvhmr_wsl') or ''
    try:
        name = select_distro(requested, [r['name'] for r in ready])
    except RuntimeError:
        name = select_distro('', [r['name'] for r in ready])
    if name:
        row = next(r for r in ready if r['name'] == name)
        if row['version'] == 1:
            out.append(check('wsl.distro', 'fail', t(f'{name} работает как WSL1', f'{name} runs as WSL1'),
                             t('WSL1 не даёт доступ к видеокарте. Переведите дистрибутив на WSL2.',
                               'WSL1 has no GPU access. Convert the distribution to WSL2.'),
                             fix('command', f'wsl --set-version {name} 2', 'Перевести на WSL2', 'Convert to WSL2'),
                             list(LOCAL), {'distro': name}))
        else:
            out.append(check('wsl.distro', 'ok', t('Дистрибутив WSL2', 'WSL2 distribution'),
                             t(f'{name} ({row["state"]})', f'{name} ({row["state"]})'), data={'distro': name}))
    elif unfinished:
        out.append(check('wsl.distro', 'warn', t('Ubuntu ещё не настроена', 'Ubuntu setup not finished'),
                         t(f'{", ".join(unfinished)} в состоянии Installing: откройте Ubuntu из меню «Пуск», задайте имя '
                           'пользователя и пароль, затем повторите проверку.',
                           f'{", ".join(unfinished)} is still Installing: open Ubuntu from the Start menu, create a user name '
                           'and password, then run the check again.'),
                         fix('tip', '', 'Откройте Ubuntu из меню «Пуск»', 'Open Ubuntu from the Start menu'), list(LOCAL)))
    else:
        others = ', '.join(r['name'] for r in rows)
        out.append(check('wsl.distro', 'fail', t('Нет Ubuntu в WSL', 'No Ubuntu in WSL'),
                         t('Нужен дистрибутив Ubuntu или Debian' + (f' (сейчас: {others}).' if others else '.'),
                           'An Ubuntu or Debian distribution is required' + (f' (found: {others}).' if others else '.')),
                         install, list(LOCAL)))
    out += check_virtualization(ctx)
    out += check_wsl_memory(ctx)
    return out


def _installing():
    from core.gvhmr_environment import INSTALLING
    return INSTALLING


def check_virtualization(ctx):
    script = ('$p=Get-CimInstance Win32_Processor | Select-Object -First 1; $c=Get-CimInstance Win32_ComputerSystem; '
              '"firmware=$($p.VirtualizationFirmwareEnabled)"; "hypervisor=$($c.HypervisorPresent)"')
    result = _cmd(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', script], 25)
    text = result['out'].casefold()
    firmware = re.search(r'firmware=(true|false)', text)
    hypervisor = re.search(r'hypervisor=(true|false)', text)
    if hypervisor and hypervisor.group(1) == 'true':
        return [check('wsl.virtualization', 'ok', t('Виртуализация включена', 'Virtualization enabled'),
                      t('Гипервизор Windows работает.', 'The Windows hypervisor is running.'))]
    if firmware and firmware.group(1) == 'true':
        return [check('wsl.virtualization', 'ok', t('Виртуализация включена', 'Virtualization enabled'),
                      t('Включена в BIOS/UEFI.', 'Enabled in BIOS/UEFI.'))]
    if firmware and firmware.group(1) == 'false':
        return [check('wsl.virtualization', 'fail', t('Виртуализация выключена в BIOS', 'Virtualization is off in BIOS'),
                      t('WSL2 требует аппаратную виртуализацию. Включите Intel VT-x / AMD-V (SVM) в BIOS/UEFI и компонент '
                        '«Платформа виртуальной машины».',
                        'WSL2 needs hardware virtualization. Enable Intel VT-x / AMD-V (SVM) in BIOS/UEFI and the '
                        '"Virtual Machine Platform" Windows feature.'),
                      fix('tip', '', 'Перезагрузите ПК, войдите в BIOS/UEFI (Del/F2) и включите Intel VT-x или SVM Mode.',
                          'Reboot, open BIOS/UEFI (Del/F2) and enable Intel VT-x or SVM Mode.'), list(LOCAL))]
    return [check('wsl.virtualization', 'info', t('Виртуализация', 'Virtualization'),
                  t('Не удалось определить, включена ли виртуализация.', 'Could not determine whether virtualization is enabled.'))]


def check_wsl_memory(ctx):
    ram = ctx.get('ram')
    if not ram:
        return []
    ram_gb = _gb(ram)
    path = Path(_env('USERPROFILE') or Path.home()) / '.wslconfig'
    try:
        text = path.read_text(encoding='utf-8', errors='replace') if path.is_file() else ''
    except OSError:
        text = ''
    configured = parse_wslconfig_memory(text)
    effective = configured if configured is not None else round(ram_gb / 2, 1)
    suggested = suggested_wsl_memory(ram_gb)
    data = {'memory_gb': effective, 'configured': configured is not None, 'suggested_gb': suggested, 'path': str(path)}
    if effective < WSL_MEMORY_GEMX and suggested > effective:
        source = t(f'в .wslconfig задано {configured} ГБ', f'.wslconfig sets {configured} GB') if configured is not None else \
            t(f'по умолчанию WSL берёт половину памяти ({effective} ГБ)', f'by default WSL gets half of RAM ({effective} GB)')
        return [check('wsl.memory', 'warn', t('Мало памяти для WSL', 'Low WSL memory limit'),
                      t(f'{source["ru"]}. GEM-X нужно около {WSL_MEMORY_GEMX} ГБ. Рекомендуется memory={suggested}GB.',
                        f'{source["en"]}. GEM-X needs about {WSL_MEMORY_GEMX} GB. memory={suggested}GB is recommended.'),
                      fix('action', 'wslconfig', f'Выделить WSL {suggested} ГБ', f'Give WSL {suggested} GB',
                          params={'memory_gb': suggested, 'swap_gb': 16}), [], data)]
    return [check('wsl.memory', 'ok', t('Память WSL', 'WSL memory'), t(f'{effective} ГБ', f'{effective} GB'), data=data)]


def check_mac_tools(ctx):
    if ctx['system'] != 'Darwin':
        return []
    result = _cmd(['xcode-select', '-p'], 10)
    if result['code'] == 0:
        return [check('mac.clt', 'ok', t('Command Line Tools', 'Command Line Tools'), t(result['out'], result['out']))]
    return [check('mac.clt', 'warn', t('Нет Command Line Tools', 'Command Line Tools missing'),
                  t('GEM-X скачивается через git из Command Line Tools. Установите их и повторите.',
                    'GEM-X is downloaded with git from the Command Line Tools. Install them and retry.'),
                  fix('command', 'xcode-select --install', 'Установить Command Line Tools', 'Install Command Line Tools'),
                  ['gemx'])]


def check_tools(ctx):
    from core import components, managed_tools
    out = []
    ffmpeg = managed_tools.find_ffmpeg()
    if ffmpeg:
        version = _cmd([ffmpeg, '-version'], 5)['out'].splitlines()[:1]
        out.append(check('tools.ffmpeg', 'ok', t('ffmpeg', 'ffmpeg'), t(version[0] if version else ffmpeg, version[0] if version else ffmpeg),
                         data={'path': ffmpeg}))
    else:
        out.append(check('tools.ffmpeg', 'warn', t('ffmpeg не найден', 'ffmpeg not found'),
                         t('Нужен для подготовки видео; Studio установит его сам.', 'Needed to prepare videos; Studio installs it.'),
                         fix('action', 'ffmpeg', 'Установить ffmpeg', 'Install ffmpeg'), ['gvhmr']))
    probe = managed_tools.home() / ('ffprobe.exe' if ctx['system'] == 'Windows' else 'ffprobe')
    ffprobe = str(probe) if probe.is_file() else shutil.which('ffprobe')
    out.append(check('tools.ffprobe', 'ok' if ffprobe else 'info', t('ffprobe', 'ffprobe'),
                     t(ffprobe or 'Не найден; устанавливается вместе с ffmpeg.', ffprobe or 'Not found; installed together with ffmpeg.'),
                     None if ffprobe else fix('action', 'ffmpeg', 'Установить ffmpeg', 'Install ffmpeg')))
    blender = components.find_blender(ctx['cfg'])
    if blender:
        out.append(check('tools.blender', 'ok', t('Blender', 'Blender'), t(blender, blender), data={'path': blender}))
    else:
        out.append(check('tools.blender', 'warn', t('Blender не найден', 'Blender not found'),
                         t('Нужен для FBX и переноса на персонажа (~400 МБ).', 'Needed for FBX and character retargeting (~400 MB).'),
                         fix('action', 'blender', 'Установить Blender', 'Install Blender'), ['blender']))
    return out


# ------------------------------------------------------------------ recommendation and runner

HARD = ('os.', 'ram', 'gpu.')


def recommend(ctx, checks):
    hard = set()
    for item in checks:
        if item['level'] == 'fail' and item['id'].startswith(HARD):
            hard.update(item['blocks'])
    soft = [item for item in checks if item['level'] == 'fail' and not item['id'].startswith(HARD)
            and set(item['blocks']) & {'gemx', 'gvhmr', 'all'}]
    if 'all' in hard:
        return {'models': [], 'reason': t('Этот компьютер не подходит для MoCapGate Studio.',
                                          'This computer is not suitable for MoCapGate Studio.')}
    gpu = ctx.get('gpu') or {}
    models = []
    if ctx['system'] == 'Darwin':
        if ctx.get('apple_silicon') and 'gemx' not in hard:
            models = ['gemx']
            reason = t('Apple Silicon: GEM-X работает локально; GVHMR — через Colab.',
                       'Apple Silicon: GEM-X runs locally; GVHMR runs in Colab.')
        else:
            reason = t('Mac на Intel: надёжнее всего GVHMR · Colab.', 'Intel Mac: GVHMR · Colab is the reliable choice.')
    elif gpu.get('kind') == 'nvidia':
        models = [m for m in LOCAL if m not in hard]
        reason = t(f'{gpu.get("name", "NVIDIA")}: локальная обработка доступна.', f'{gpu.get("name", "NVIDIA")}: local processing is available.')
        if 'gvhmr' in hard and 'gemx' not in hard:
            reason = t('RTX 50 / мало ресурсов для GVHMR: используйте GEM-X.', 'RTX 50 / not enough resources for GVHMR: use GEM-X.')
        if not models:
            reason = t('Видеокарты или памяти недостаточно для локальных моделей.', 'The GPU or memory is not enough for local models.')
    else:
        reason = t('Нет NVIDIA: обрабатывайте видео в GVHMR · Colab (бесплатный GPU Google).',
                   'No NVIDIA GPU: process videos with GVHMR · Colab (free Google GPU).')
    if models and soft:
        reason = t(reason['ru'] + ' Сначала устраните ошибки выше: ' + ', '.join(i['id'] for i in soft) + '.',
                   reason['en'] + ' Fix the errors above first: ' + ', '.join(i['id'] for i in soft) + '.')
    if not models or soft:
        models.append('gvhmr-colab')
    return {'models': models, 'reason': reason}


def _error(cid, exc):
    message = f'{type(exc).__name__}: {exc}'[:400]
    return check(cid, 'warn', t('Проверка не выполнена', 'Check failed to run'),
                 t(f'Внутренняя ошибка проверки: {message}', f'Internal check error: {message}'))


CHECKS = [('os', check_os), ('ram', check_ram), ('disk', check_disk), ('library', check_library), ('home', check_home),
          ('network.proxy', check_proxy), ('gpu', check_gpu), ('wsl', check_wsl), ('mac.clt', check_mac_tools),
          ('tools', check_tools)]


def _context(cfg, timeout):
    ctx = {'cfg': cfg, 'timeout': timeout}
    for key, probe in (('system', _system), ('machine', _machine)):
        try:
            ctx[key] = probe()
        except Exception:
            ctx[key] = ''
    for key, probe in (('build', lambda: _windows_build() if ctx['system'] == 'Windows' else None),
                       ('mac_version', lambda: _mac_version() if ctx['system'] == 'Darwin' else None),
                       ('apple_silicon', _apple_silicon), ('ram', _ram_bytes), ('library', lambda: _library(cfg)),
                       ('runtime', _runtime_dir)):
        try:
            ctx[key] = probe()
        except Exception:
            ctx[key] = None
    ctx['library'] = ctx['library'] or Path.home() / 'Documents' / 'MoCapGate Takes'
    ctx['runtime'] = ctx['runtime'] or Path.home()
    return ctx


def run(cfg=None, network=True, timeout=6):
    """All checks in parallel threads; never raises. A check still running at the deadline becomes a warning."""
    try:
        if cfg is None:
            from core import settings
            cfg = settings.load()
    except Exception:
        cfg = {}
    ctx = _context(cfg or {}, timeout)
    plan = list(CHECKS) + ([('network', check_network)] if network else [])
    results = {}

    def worker(name, function):
        try:
            results[name] = function(ctx)
        except Exception as exc:
            results[name] = [_error(name, exc)]

    threads = [(name, threading.Thread(target=worker, args=(name, function), daemon=True)) for name, function in plan]
    for _, thread in threads:
        thread.start()
    deadline = time.monotonic() + max(45, timeout * 3)
    for _, thread in threads:
        thread.join(max(0.0, deadline - time.monotonic()))
    checks = []
    for name, _ in plan:
        if name in results:
            checks += results[name]
        else:
            checks.append(check(name, 'warn', t('Проверка не успела завершиться', 'Check timed out'),
                                t('Повторите проверку позже.', 'Run the check again later.')))
    try:
        advice = recommend(ctx, checks)
    except Exception as exc:
        advice = {'models': ['gvhmr-colab'], 'reason': t(f'Ошибка рекомендации: {exc}', f'Recommendation error: {exc}')}
    gpu = ctx.get('gpu') or {}
    info = {'system': ctx['system'], 'machine': ctx['machine'], 'release': platform.release(),
            'windows_build': ctx.get('build'), 'macos': ctx.get('mac_version'), 'apple_silicon': bool(ctx.get('apple_silicon')),
            'python': platform.python_version(), 'ram_gb': _gb(ctx['ram']) if ctx.get('ram') else None,
            'library': str(ctx['library']), 'runtime': str(ctx['runtime']),
            'gpu': {k: (f'{v[0]}.{v[1]}' if k == 'cap' and v else v) for k, v in gpu.items()}}
    return {'platform': info, 'checks': checks, 'recommend': advice}


if __name__ == '__main__':
    import json
    print(json.dumps(run(), ensure_ascii=False, indent=1))
