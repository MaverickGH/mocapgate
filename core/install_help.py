"""Install troubleshooting knowledge base: error output / log text → concrete advice (pure stdlib).

advise(text) -> [{"id", "ru", "en", "fix": {"kind": action|command|link|tip, "value", "label": {ru,en}} | None}]
Rules are ordered from specific to generic; every rule appears at most once. Matching is case-insensitive
and covers both English tool output and the Russian messages MoCapGate itself produces.
"""
from __future__ import annotations

import re

COLAB_URL = 'https://colab.research.google.com/'
NVIDIA_DRIVERS = 'https://www.nvidia.com/Download/index.aspx'
SMPLX_URL = 'https://smpl-x.is.tue.mpg.de'
LONG_PATHS_COMMAND = ('New-ItemProperty -Path "HKLM:\\SYSTEM\\CurrentControlSet\\Control\\FileSystem" '
                      '-Name "LongPathsEnabled" -Value 1 -PropertyType DWORD -Force')
ENABLE_WSL_COMMAND = 'wsl --install --no-distribution'


def _fix(kind, value, ru, en):
    return {'kind': kind, 'value': value, 'label': {'ru': ru, 'en': en}}


# (id, patterns, ru, en, fix)
RULES = [
    ('wsl_virtualization', [r'0x80370102', r'0x80370114', r'hcs_e_hyperv_not_installed', r'virtualization.*(disabled|not enabled|bios)',
                            r'enable.*virtuali[sz]ation', r'виртуализац'],
     'Включите аппаратную виртуализацию: Intel VT-x или AMD-V (SVM Mode) в BIOS/UEFI, затем компонент Windows '
     '«Платформа виртуальной машины» и перезагрузите ПК.',
     'Enable hardware virtualization: Intel VT-x or AMD-V (SVM Mode) in BIOS/UEFI, then the Windows feature '
     '"Virtual Machine Platform", and reboot.',
     _fix('command', 'dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart',
          'PowerShell от администратора, затем перезагрузка', 'PowerShell as administrator, then reboot')),
    ('wsl_feature_off', [r'0x8007019e', r'0x8000000d', r'0x80040321', r'wsl_e_wsl_optional_component_required',
                         r'windows subsystem for linux (has no installed|is not (installed|enabled))',
                         r'optional component.*not enabled', r'компонент wsl выключен', r'подсистема windows для linux не (установлена|включена)'],
     'Компонент WSL не включён. Выполните в PowerShell от администратора «wsl --install» и перезагрузите компьютер.',
     'The WSL feature is not enabled. Run "wsl --install" in PowerShell as administrator and reboot.',
     _fix('command', 'wsl --install', 'PowerShell от администратора, затем перезагрузка', 'PowerShell as administrator, then reboot')),
    ('wsl_kernel', [r'0x80070422', r'0x800701bc', r'kernel component', r'wsl 2 requires an update to its kernel', r'компонент ядра',
                    r'ядр[ао] wsl'],
     'Обновите ядро WSL: выполните «wsl --update» (служба «Установщик Windows»/Update должна быть включена) и перезапустите ПК.',
     'Update the WSL kernel: run "wsl --update" (Windows Update services must be enabled) and restart the PC.',
     _fix('command', 'wsl --update', 'Обновить WSL', 'Update WSL')),
    ('wsl_uac', [r'не запустил установку wsl', r'подтвердите запрос администратора', r'operation was canceled by the user',
                 r'requested operation requires elevation', r'0x800702e4'],
     'Установка WSL требует прав администратора: подтвердите запрос Windows (UAC) и повторите.',
     'WSL installation needs administrator rights: accept the Windows (UAC) prompt and retry.',
     _fix('action', 'wsl', 'Повторить установку WSL', 'Retry WSL installation')),
    ('wsl_installing', [r'^\s*\*?\s*\S+\s+(installing|установка|устанавливается)\s+[12]\s*$', r'state.*installing', r'ещё installing', r'незаверш[её]нн', r'нет готового дистрибутива wsl',
                        r'завершите (его )?первый запуск', r'create a default unix user account'],
     'Ubuntu ещё не настроена: откройте Ubuntu из меню «Пуск», задайте имя пользователя и пароль, закройте окно и повторите.',
     'Ubuntu is not set up yet: open Ubuntu from the Start menu, create a user name and password, close it and retry.',
     _fix('tip', '', 'Откройте Ubuntu из меню «Пуск»', 'Open Ubuntu from the Start menu')),
    ('wsl_hung', [r'wsl не отвечает', r'wsl.*(timed out|timeout|not responding)', r'timeoutexpired.*wsl', r'wsl.*timeoutexpired',
                  r'0x8007274c', r'the operation timed out because a response was not received from the virtual machine'],
     'WSL завис: выполните «wsl --shutdown» в PowerShell или перезагрузите компьютер, затем повторите.',
     'WSL is hung: run "wsl --shutdown" in PowerShell or reboot, then retry.',
     _fix('command', 'wsl --shutdown', 'Перезапустить WSL', 'Restart WSL')),
    ('wsl_missing', [r'wsl\.exe.*(cannot find the file|не удается найти указанный файл|no such file|not found)',
                     r'(cannot find the file specified|не удается найти указанный файл).*wsl',
                     r"winerror 2\b.*wsl", r'wsl.*winerror 2\b', r'дистрибутив wsl не найден', r'установите и запустите ubuntu / wsl2',
                     r'no installed distributions', r'нет установленных дистрибутивов', r'wsl_e_default_distro_not_found'],
     'WSL или Ubuntu не установлены. Нажмите «Установить WSL» в «Модели и инструменты» и перезагрузите ПК.',
     'WSL or Ubuntu is not installed. Click "Install WSL" in Models & tools and reboot.',
     _fix('action', 'wsl', 'Установить WSL и Ubuntu', 'Install WSL and Ubuntu')),
    ('apt_lock', [r'could not get lock', r'unable to acquire the dpkg frontend lock', r'dpkg was interrupted', r'/var/lib/dpkg/lock'],
     'Ubuntu сейчас обновляет пакеты (apt занят). Подождите 5–10 минут и повторите установку.',
     'Ubuntu is updating packages (apt is busy). Wait 5–10 minutes and retry the installation.',
     _fix('command', 'wsl -u root -e dpkg --configure -a', 'Если не помогло: восстановить dpkg', 'If it persists: repair dpkg')),
    ('gvhmr_rtx50', [r'no kernel image is available for execution on the device', r'sm_120', r'compute capability 12',
                     r'rtx 50-сер', r'not compatible with the current pytorch installation'],
     'GVHMR (PyTorch 2.3 / CUDA 12.1) не поддерживает RTX 50-й серии. Используйте GEM-X или GVHMR · Colab.',
     'GVHMR (PyTorch 2.3 / CUDA 12.1) does not support RTX 50-series GPUs. Use GEM-X or GVHMR · Colab.',
     _fix('tip', '', 'Выберите GEM-X в настройках обработки', 'Choose GEM-X in processing settings')),
    ('cuda_oom', [r'cuda out of memory', r'outofmemoryerror', r'cudnn_status_alloc_failed', r'cuda error: out of memory'],
     'Не хватило видеопамяти: обработайте более короткое видео или в меньшем разрешении, включите быстрый режим и закройте игры/браузер.',
     'Out of GPU memory: process a shorter or lower-resolution video, enable fast mode and close games/browsers.',
     _fix('tip', '', 'Короче видео, ниже разрешение, быстрый режим', 'Shorter video, lower resolution, fast mode')),
    ('ram_oom', [r'\bkilled\b', r'exit (code|status) 137', r'код 137', r'returned non-zero exit status 137', r'memoryerror',
                 r'cannot allocate memory', r'out of memory', r'\boom[- ]?kill', r'\boom\b'],
     'Процессу не хватило оперативной памяти. В настройках дубля поставьте «Разрешение для распознавания» 1280 (особенно для 4K с телефона) '
     'и «Обработка частями», выберите режим «Быстро (ONNX)»; выделите WSL больше памяти в .wslconfig. Проверить, сколько нужно, — '
     '«Модели и инструменты» → «Тест производительности».',
     'The process ran out of RAM. In the take settings set “Recognition resolution” to 1280 (especially for 4K phone video) and '
     '“Process in parts”, choose “Fast (ONNX)”; give WSL more memory in .wslconfig. To see how much is needed: Models & tools → '
     '“Performance test”.',
     _fix('action', 'wslconfig', 'Увеличить память WSL', 'Increase WSL memory')),
    ('disk_full', [r'no space left on device', r'нужно не меньше \d+ ГБ свободного места', r'not enough (free )?(disk )?space',
                   r'needs at least \d+ gb of free disk space', r'winerror 112', r'недостаточно места на диске', r'errno 28'],
     'Закончилось место на диске. Освободите место (на Windows — на диске с профилем пользователя, где хранится WSL) и повторите: '
     'загрузка продолжится.',
     'The disk is full. Free up space (on Windows, on the user-profile drive where WSL lives) and retry: the download resumes.',
     _fix('tip', '', 'Освободите 30+ ГБ и повторите', 'Free 30+ GB and retry')),
    ('ssl', [r'certificate_verify_failed', r'certificate verify failed', r'self[- ]signed certificate', r'sslcertverificationerror',
             r'unable to get local issuer certificate', r'ssl: wrong_version_number', r'tlsv1 alert'],
     'HTTPS-сертификат подменён: обычно это проверка HTTPS в антивирусе или корпоративный прокси. Добавьте MoCapGate в исключения '
     'веб-защиты или используйте другую сеть.',
     'The HTTPS certificate is intercepted, usually by antivirus HTTPS scanning or a corporate proxy. Exclude MoCapGate from web '
     'protection or use another network.',
     _fix('tip', '', 'Исключение в антивирусе или другая сеть', 'Antivirus exclusion or another network')),
    ('rate_limit', [r'http (error )?429', r'too many requests', r'ответил http 429', r'rate limit',
                    r'(huggingface|github|hf\.co).*\b403\b', r'\b403\b.*(huggingface|github|hf\.co)', r'ответил http 403',
                    r'google drive: скачивание ограничено', r'too many users have viewed or downloaded'],
     'Сервер временно ограничил скачивание. Подождите 10–30 минут и повторите — загрузка продолжится с места остановки.',
     'The server temporarily limited downloads. Wait 10–30 minutes and retry — the download resumes where it stopped.',
     _fix('action', 'retry', 'Повторить позже', 'Retry later')),
    ('download_broken', [r'загрузка прервана', r'соединение прервано', r'incompleteread', r'connection (reset|aborted)',
                         r'remote end closed connection', r'temporary failure in name resolution', r'getaddrinfo failed',
                         r'name or service not known', r'nodename nor servname', r'urlopen error', r'read timed out',
                         r'connecttimeout', r'network is unreachable'],
     'Соединение оборвалось. Проверьте интернет/VPN и повторите установку — скачивание продолжится.',
     'The connection dropped. Check the internet/VPN and retry — the download resumes.',
     _fix('action', 'retry', 'Повторить установку', 'Retry installation')),
    ('download_corrupt', [r'архив повреждён', r'не докачан', r'скачан не файл модели', r'не прошли проверку размера',
                          r'sha-?256', r'badzipfile', r'неверный размер файла', r'размер больше ожидаемого',
                          r'неверный lfs-указатель', r'не прошёл sha-256'],
     'Файл скачался повреждённым. Повторите установку: повреждённая копия будет скачана заново.',
     'The file was downloaded corrupted. Retry the installation: the broken copy is downloaded again.',
     _fix('action', 'retry', 'Повторить установку', 'Retry installation')),
    ('git_lfs', [r'git-lfs', r'git lfs', r'smudge filter lfs failed', r'this repository is over its data quota',
                 r'version https://git-lfs'],
     'Ошибка Git LFS: большие файлы репозитория не скачались. Повторите установку позже; при квоте GitHub подождите сутки.',
     'Git LFS error: the repository\'s large files did not download. Retry later; if GitHub reports a quota, wait a day.',
     _fix('action', 'retry', 'Повторить установку', 'Retry installation')),
    ('access_denied', [r'access is denied', r'winerror 5\b', r'permissionerror', r'отказано в доступе', r'errno 13',
                       r'being used by another process', r'winerror 32', r'файл используется другим процессом'],
     'Файл заблокирован или нет доступа: закройте Studio, Blender и плееры, добавьте папку MoCapGate в исключения антивируса '
     'и повторите.',
     'A file is locked or access is denied: close Studio, Blender and players, exclude the MoCapGate folder from antivirus '
     'and retry.',
     _fix('tip', '', 'Закрыть программы и добавить исключение антивируса', 'Close apps and add an antivirus exclusion')),
    ('long_path', [r'winerror 206', r'filename or extension is too long', r'path too long', r'имя файла или его расширение имеет '
                   r'слишком большую длину', r'filename too long'],
     'Слишком длинный путь. Включите длинные пути Windows (команда ниже) или выберите короткую папку дублей, например C:\\MoCap.',
     'The path is too long. Enable Windows long paths (command below) or choose a short takes folder such as C:\\MoCap.',
     _fix('command', LONG_PATHS_COMMAND, 'PowerShell от администратора', 'PowerShell as administrator')),
    ('gvhmr_vo', [r'cam2_from_cam1', r"'nonetype' object has no attribute 'matrix'", r'simple_vo'],
     'GVHMR не смог оценить движение камеры на части кадров (однотонный фон, смаз, мало деталей). С 0.3.3-beta.6 такие '
     'кадры не роняют обработку — обновите Studio. Если камера стояла на месте, включите «Камера неподвижна»: шаг '
     'оценки движения камеры тогда не нужен и обработка быстрее.',
     'GVHMR could not estimate camera motion on some frames (plain background, blur, few details). Since 0.3.3-beta.6 '
     'such frames no longer stop processing — update Studio. If the camera did not move, enable “Static camera”: the '
     'camera-motion step is skipped and processing is faster.', None),
    ('warp_driver', [r'insufficient cuda driver version', r'warp .*initialized.*cuda toolkit 1[3-9]',
                     r'device_from_torch', r'runtime\.cuda_devices\[', r'alignvectorswarp'],
     'Библиотека Warp (её использует GEM-X) собрана под CUDA 13 и с вашим драйвером работает только на процессоре — '
     'медленнее, но не причина сбоя. Обновите драйвер NVIDIA до версии 580 или новее (поддерживает CUDA 13) и перезагрузите ПК; '
     'или переустановите GEM-X — установщик подберёт Warp под CUDA 12.',
     'The Warp library (used by GEM-X) is built for CUDA 13 and with your driver runs on the CPU only — slower, but not '
     'the cause of a crash. Update the NVIDIA driver to 580 or newer (CUDA 13) and reboot, or reinstall GEM-X — setup '
     'picks a CUDA 12 build of Warp.', _fix('link', 'https://www.nvidia.com/Download/index.aspx', 'Драйвер NVIDIA', 'NVIDIA driver')),
    ('nvidia_driver', [r'cuda driver version is insufficient', r'nvidia-smi.*(not found|not recognized|не найден|не является)',
                       r'(not found|не найден).*nvidia-smi', r'found no nvidia driver', r'nvidia driver on your system is too old',
                       r'не найдена nvidia', r'требует nvidia', r'cuda_error_no_device', r'no cuda gpus are available',
                       r'torch\.cuda\.is_available\(\) is false', r'libcuda\.so.*cannot open'],
     'Нужен драйвер NVIDIA версии 535 или новее. Установите его с сайта NVIDIA, перезагрузите ПК и перезапустите Studio. '
     'Без NVIDIA используйте GVHMR · Colab.',
     'NVIDIA driver 535 or newer is required. Install it from NVIDIA, reboot and restart Studio. '
     'Without NVIDIA use GVHMR · Colab.',
     _fix('link', NVIDIA_DRIVERS, 'Скачать драйвер NVIDIA', 'Download NVIDIA driver')),
    ('xcode_clt', [r'xcrun: error: invalid active developer path', r'xcode-select', r'command line tools', r'git недоступен'],
     'Установите Command Line Tools для macOS («xcode-select --install») и повторите установку GEM-X.',
     'Install the macOS Command Line Tools ("xcode-select --install") and retry the GEM-X installation.',
     _fix('command', 'xcode-select --install', 'Установить Command Line Tools', 'Install Command Line Tools')),
    ('smplx', [r'smplx_neutral', r'(модел[ьи]|файл|массив вершин) smpl-x', r'smpl-x (neutral|повреж)',
               r'smpl-?x.*(not found|missing|не найден)', r'нужна smpl-x', r'не является моделью smpl-x'],
     'Нужна модель SMPL-X NEUTRAL (SMPLX_NEUTRAL.npz) с сайта SMPL-X после регистрации. Загрузите её в «Модели и инструменты».',
     'The SMPL-X NEUTRAL model (SMPLX_NEUTRAL.npz) from the SMPL-X site is required after registration. Upload it in Models & tools.',
     _fix('link', SMPLX_URL, 'Сайт SMPL-X', 'SMPL-X website')),
    ('blender_missing', [r'blender not found', r'blender не найден', r'нужен blender', r'нужны blender', r'no blender'],
     'Установите Blender в «Модели и инструменты» (~400 МБ) или укажите путь к своему Blender в Настройках.',
     'Install Blender in Models & tools (~400 MB) or set the path to your Blender in Settings.',
     _fix('action', 'blender', 'Установить Blender', 'Install Blender')),
    ('ffmpeg_missing', [r'нужен ffmpeg', r'не найден ffmpeg', r'установите ffmpeg', r'ffmpeg(\.exe)?: (command )?not found',
                        r'ffmpeg.*(is not recognized|не является)', r"no such file or directory: '?ffmpeg"],
     'Установите ffmpeg в «Модели и инструменты».', 'Install ffmpeg in Models & tools.',
     _fix('action', 'ffmpeg', 'Установить ffmpeg', 'Install ffmpeg')),
    ('video_corrupt', [r'moov atom not found', r'invalid data found when processing input', r'нет видеодорожки',
                       r'не содержит временных меток', r'could not find codec parameters'],
     'Видео повреждено или не докачано. Перекодируйте его или запишите заново (MP4 H.264), затем добавьте снова.',
     'The video is corrupt or incomplete. Re-encode or re-record it (MP4 H.264) and add it again.',
     _fix('tip', '', 'Перекодировать в MP4 H.264', 'Re-encode to MP4 H.264')),
    ('no_person', [r'человек не найден', r'не нашёл людей', r'не нашёл участников', r'не нашёл устойчивых траекторий',
                   r'no person', r'no people'],
     'В кадре не найден человек: нужно, чтобы тело было видно целиком, хорошее освещение и неподвижная камера.',
     'No person was found: keep the whole body in frame, use good lighting and a steady camera.',
     _fix('tip', '', 'Снимите человека целиком', 'Film the whole body')),
    ('model_terms', [r'accept-model-terms', r'подтвердите условия gvhmr'],
     'Подтвердите лицензии GVHMR и моделей в окне установки, затем повторите.',
     'Accept the GVHMR and model licences in the installer, then retry.',
     _fix('action', 'gvhmr', 'Установить GVHMR', 'Install GVHMR')),
    ('linux_deps', [r'apt-get и pkexec', r'install git, ffmpeg, python3-venv'],
     'Установите системные пакеты вручную: sudo apt install git ffmpeg python3-venv python3-dev build-essential libgl1 libglib2.0-0.',
     'Install system packages manually: sudo apt install git ffmpeg python3-venv python3-dev build-essential libgl1 libglib2.0-0.',
     _fix('command', 'sudo apt install -y git ffmpeg python3-venv python3-dev build-essential libgl1 libegl1 libglib2.0-0',
          'Выполнить в терминале', 'Run in a terminal')),
    ('colab_only', [r'требует linux x64', r'requires linux x64', r'на mac выберите gvhmr · colab'],
     'На этом компьютере локальный GVHMR недоступен — используйте GVHMR · Colab.',
     'Local GVHMR is not available on this computer — use GVHMR · Colab.',
     _fix('link', COLAB_URL, 'Открыть Colab', 'Open Colab')),
    ('mediapipe_missing', [r'трекер mediapipe не установлен', r'вспомогательный трекер', r'no module named .?mediapipe'],
     'Установите MediaPipe в «Модели и инструменты» (нужен для кистей и лица).',
     'Install MediaPipe in Models & tools (needed for hands and face).',
     _fix('action', 'mediapipe', 'Установить MediaPipe', 'Install MediaPipe')),
    ('gemx_missing', [r'установите gem-x', r'установка gem-x не завершена'],
     'Установка GEM-X не завершена. Нажмите «Установить» ещё раз — загрузка продолжится.',
     'GEM-X installation is incomplete. Click Install again — the download resumes.',
     _fix('action', 'gemx', 'Установить GEM-X', 'Install GEM-X')),
    ('gvhmr_missing', [r'установка gvhmr не завершена', r'gvhmr на этом компьютере не готов'],
     'Установка GVHMR не завершена. Нажмите «Установить» ещё раз — загрузка продолжится.',
     'GVHMR installation is incomplete. Click Install again — the download resumes.',
     _fix('action', 'gvhmr', 'Установить GVHMR', 'Install GVHMR')),
    ('module_missing', [r'no module named', r'modulenotfounderror', r'importerror', r'не удалось создать окружение python',
                        r'dll load failed'],
     'Окружение компонента неполное. Переустановите компонент в «Модели и инструменты» — повреждённое окружение будет пересоздано.',
     'The component environment is incomplete. Reinstall the component in Models & tools — a broken environment is recreated.',
     _fix('action', 'retry', 'Переустановить компонент', 'Reinstall the component')),
]

# A generic rule is dropped when a more specific one already explains the same failure.
SUPPRESS = {'download_broken': {'ssl', 'rate_limit'}, 'ram_oom': {'cuda_oom'}, 'module_missing': {'mediapipe_missing'},
            'wsl_missing': {'wsl_feature_off'}, 'download_corrupt': {'git_lfs'}}

_COMPILED = [(rid, re.compile('|'.join(f'(?:{p})' for p in patterns), re.IGNORECASE | re.MULTILINE), ru, en, fix)
             for rid, patterns, ru, en, fix in RULES]


def advise(text):
    """Advice for an error message or log tail; [] when nothing matches. Never raises."""
    try:
        if isinstance(text, bytes):
            text = text.decode('utf-8', errors='replace')
        if isinstance(text, (list, tuple)):
            text = '\n'.join(str(line) for line in text)
        text = str(text or '').replace('\x00', '')
    except Exception:
        return []
    if not text.strip():
        return []
    hits = []
    for rid, pattern, ru, en, fix in _COMPILED:
        try:
            hit = pattern.search(text)
        except Exception:
            hit = None
        if hit and rid not in {h[0] for h in hits}:
            hits.append((rid, ru, en, fix))
    seen = {h[0] for h in hits}  # подавление — после всех совпадений, независимо от порядка правил
    return [{'id': rid, 'ru': ru, 'en': en, 'fix': dict(fix) if fix else None}
            for rid, ru, en, fix in hits if not SUPPRESS.get(rid, set()) & seen]
