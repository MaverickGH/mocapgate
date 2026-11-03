# Решение проблем установки

[English version](troubleshooting.en.md) · [Установка](install.md)

Сначала: **«Модели и инструменты» → «Проверить компьютер»** (или `CHECK-COMPUTER.cmd` из quickstart).
Большинство проблем там видно сразу, с кнопкой или командой исправления.
Команды с пометкой **(администратор)** выполняются в PowerShell, открытом через
правый щелчок по «Пуск» → «Терминал (администратор)» / «Windows PowerShell (администратор)».
Остальные — в обычном PowerShell. MoCapGate сам эти команды не выполняет.

## Быстрая таблица

| Симптом / сообщение | Причина | Что сделать |
|---|---|---|
| «Windows защитила ваш компьютер» | Сборка не подписана сертификатом (SmartScreen не знает издателя) | [SmartScreen](#smartscreen) |
| «Архив не распакован…», код 4, нет `mocapgate.py` / `python\python.exe` | Запуск из ZIP или распаковка не до конца | [Архив](#архив-распакован-не-полностью) |
| `path too long`, `FileNotFoundError` на длинном пути | Путь длиннее 260 символов | [Длинные пути](#слишком-длинный-путь) |
| Файлы пропадают, «облачный файл недоступен», медленно | Папка в OneDrive | [OneDrive](#onedrive) |
| Файлы удаляются после распаковки, `Access is denied`, `CERTIFICATE_VERIFY_FAILED` | Антивирус блокирует или проверяет HTTPS | [Антивирус](#антивирус) |
| `timed out`, `Name or service not known`, `ProxyError`, 407 | Нет интернета или нужен прокси | [Интернет и прокси](#интернет-и-прокси) |
| `0x80370102`, `0x8007019e`, `WSL 1`, Ubuntu «Installing», WSL завис | Проблемы WSL | [WSL](#wsl) |
| `Could not get lock /var/lib/dpkg/lock-frontend` | В Ubuntu идёт другое обновление | [apt lock](#apt-занят) |
| `No space left on device`, «нужно не меньше … ГБ», код 5 | Мало места | [Диск](#мало-места-на-диске) |
| «Драйвер … нужен 535 или новее», `CUDA driver version is insufficient` | Старый драйвер NVIDIA | [Драйвер](#драйвер-nvidia) |
| `CUDA out of memory`, `Killed`, процесс завершился без ошибки | Не хватает видеопамяти или памяти WSL | [Память](#не-хватает-памяти) |
| «RTX 50-серия не поддерживается» (GVHMR) | GVHMR собран под PyTorch 2.3 / CUDA 12.1 | [RTX 50](#rtx-50-и-gvhmr) |
| «Неверный файл SMPL-X», `SMPLX_NEUTRAL.npz` не найден | Выбран не тот файл | [SMPL-X](#smpl-x) |
| «Blender is required for FBX», Blender не найден | Blender не установлен или путь не найден | [Blender](#blender) |
| «Studio запущен», код 3 | Приложение открыто во время установки | Закройте MoCapGate Studio и запустите INSTALL.cmd снова |
| Mac: «не удаётся открыть, так как разработчик не подтверждён» | Gatekeeper, сборка не подписана | [Mac](#mac-gatekeeper) |
| Mac: `xcrun: error: invalid active developer path` | Нет Command Line Tools | [Mac](#mac-command-line-tools) |
| Установка прервалась | Обрыв сети, перезагрузка, отмена | [Повтор](#как-повторить-прерванную-установку) |

Коды выхода INSTALL.cmd / setup: `0` готово, `1` ошибка шага (см. сообщение и журнал), `3` Studio запущен,
`4` архив не распакован или неполный, `5` мало места, `6` не 64-битная Windows или старый PowerShell.

## SmartScreen

Сборки MoCapGate не подписаны платным сертификатом, поэтому Windows показывает предупреждение.
Это не результат проверки на вирусы. Если архив скачан со [страницы релизов](https://github.com/MaverickGH/app-releases/releases):
«Подробнее» → «Выполнить в любом случае». Можно снять пометку «скачано из интернета» с архива **до** распаковки:

```powershell
Unblock-File -Path "$env:USERPROFILE\Downloads\MoCapGate-*-quickstart.zip"
```

## Архив распакован не полностью

Двойной щелчок по файлу внутри ZIP запускает его из временной папки без остальных файлов.
Правой кнопкой по ZIP → «Извлечь все…» → например `C:\MoCapGate`, затем INSTALL.cmd из этой папки.
Или в PowerShell:

```powershell
Expand-Archive -Path "$env:USERPROFILE\Downloads\MoCapGate-*-quickstart.zip" -DestinationPath C:\MoCapGate -Force
```

Если после распаковки файлов не хватает — их удалил антивирус (см. ниже).

## Слишком длинный путь

Распакуйте ближе к корню диска (`C:\MoCapGate`). Или включите длинные пути Windows **(администратор)**,
затем перезайдите в Windows:

```powershell
New-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" -Name "LongPathsEnabled" -Value 1 -PropertyType DWORD -Force
```

## OneDrive

Не распаковывайте пакет в OneDrive. Если «Документы» синхронизируются, библиотека дублей
`Документы\MoCapGate Takes` тоже уходит в облако: смените папку библиотеки в «Настройках»
(например, `C:\MoCapGate Takes`) или в OneDrive выберите для неё «Всегда хранить на этом устройстве».

## Антивирус

Добавьте исключения для папок приложения, компонентов и дублей. Для Microsoft Defender **(администратор)**:

```powershell
Add-MpPreference -ExclusionPath "$env:LOCALAPPDATA\MoCapGate Studio"
Add-MpPreference -ExclusionPath "$env:USERPROFILE\.cache\mocapgate"
Add-MpPreference -ExclusionPath "$env:USERPROFILE\Documents\MoCapGate Takes"
```

Делайте это только для пакета со страницы релизов. Для других антивирусов — те же папки в их настройках.
Ошибка `CERTIFICATE_VERIFY_FAILED` / `SSL: certificate verify failed` обычно означает, что антивирус
проверяет HTTPS-трафик («веб-защита», «сканирование HTTPS/SSL»). Временно выключите эту функцию на
время установки или добавьте `python.exe` и `uv.exe` из `%LOCALAPPDATA%\MoCapGate Studio\mocapgate` в исключения
веб-защиты, затем нажмите установку снова.

## Интернет и прокси

Проверка доступа к серверам загрузки:

```powershell
Test-NetConnection github.com -Port 443
curl.exe -I https://huggingface.co
curl.exe -I https://download.blender.org
```

Если сеть работает только через прокси, задайте его для своей учётной записи и перезапустите Studio
(адрес и порт — от вашего администратора):

```powershell
setx HTTPS_PROXY http://proxy.example:3128
setx HTTP_PROXY http://proxy.example:3128
```

Для WSL на Windows 11 22H2+ можно включить наследование сетевых настроек в `%USERPROFILE%\.wslconfig`:

```ini
[wsl2]
networkingMode=mirrored
autoProxy=true
```

затем `wsl --shutdown`. VPN, блокирующий WSL, на время установки лучше отключить.

## WSL

| Сообщение | Что сделать |
|---|---|
| `0x80370102` | Включите виртуализацию **Intel VT-x / AMD SVM** в BIOS/UEFI; проверьте: Диспетчер задач → Производительность → ЦП → «Виртуализация». Затем включите компонент **(администратор)**: `dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart` и перезагрузитесь |
| `0x8007019e`, `WSL_E_WSL_OPTIONAL_COMPONENT_REQUIRED` | Компонент WSL не включён **(администратор)**: `dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart`, перезагрузка |
| «Требуется обновление ядра», `0x800701bc`, старая версия WSL | `wsl --update` (Windows может спросить разрешение администратора) |
| Ubuntu в состоянии `Installing` | Откройте «Ubuntu» из меню «Пуск» и завершите создание пользователя. Проверка: `wsl -l -v` |
| `VERSION 1` в `wsl -l -v` | `wsl --set-version Ubuntu 2` и `wsl --set-default-version 2` |
| WSL не отвечает, установка зависла | `wsl --shutdown`, затем снова «Установить всё рекомендуемое» |

Полезные команды:

```powershell
wsl --status
wsl -l -v
wsl --update
wsl --shutdown
wsl --set-version Ubuntu 2
```

Если дистрибутив испорчен, можно поставить ещё один, не трогая старый: `wsl --install -d Ubuntu-24.04`,
затем указать его имя в «Настройках» → «Предпочтения и дополнительные пути» → «Ручные пути GVHMR» → «Окружение» → «WSL».
Редкие ошибки обслуживания Windows (`0x800f0922`, откат компонентов) — см. [восстановление GVHMR](gvhmr-install-recovery.ru.md).

## apt занят

`Could not get lock /var/lib/dpkg/lock-frontend` — в Ubuntu идёт автообновление. Установщик ждёт до 10 минут.
Если не помогло — посмотрите, что работает, и восстановите прерванную установку пакетов:

```powershell
wsl -d Ubuntu -u root -- bash -c "ps aux | grep -E 'apt|dpkg' | grep -v grep"
wsl -d Ubuntu -u root -- dpkg --configure -a
```

## Мало места на диске

Базовой установке нужно 5 ГБ, GEM-X около 30 ГБ, GVHMR около 15 ГБ на диске профиля пользователя
(там же диск Ubuntu). Проверка: `Get-PSDrive C`. Освободите место («Очистка диска», «Удалить старую корзину»
в MoCapGate) или перенесите Ubuntu на другой диск (новые версии WSL, после `wsl --update`):

```powershell
wsl --shutdown
wsl --manage Ubuntu --move D:\WSL\Ubuntu
```

## Драйвер NVIDIA

Нужен драйвер **535 или новее**. Проверка версии в Windows и внутри WSL:

```powershell
nvidia-smi
wsl -d Ubuntu -- nvidia-smi
```

Установите свежий драйвер с [nvidia.com](https://www.nvidia.com/Download/index.aspx) или через NVIDIA App
в Windows. Драйвер NVIDIA **внутри** Ubuntu ставить не нужно — WSL использует драйвер Windows.

## Не хватает памяти

- `CUDA out of memory`: возьмите более короткое видео или меньшее разрешение, уменьшите «Сколько людей»,
  закройте игры и другие программы, использующие видеокарту. Для GEM-X нужно 8 ГБ видеопамяти.
- `Killed` или обработка обрывается без причины: WSL по умолчанию получает половину ОЗУ. «Проверить компьютер»
  предлагает кнопку «Выделить WSL N ГБ». Вручную — файл `%USERPROFILE%\.wslconfig`:

```ini
[wsl2]
memory=16GB
swap=16GB
```

затем `wsl --shutdown` и повторите обработку. Не задавайте больше, чем ОЗУ минус 4 ГБ.

## RTX 50 и GVHMR

GVHMR работает на PyTorch 2.3 / CUDA 12.1, который не поддерживает видеокарты RTX 50 (Blackwell).
На них используйте **GEM-X** или **GVHMR · Colab**.

## SMPL-X

Нужен файл `SMPLX_NEUTRAL.npz` из архива SMPL-X с [smpl-x.is.tue.mpg.de](https://smpl-x.is.tue.mpg.de/download.php)
(можно выбрать сам скачанный ZIP). Не подходят модели SMPL / SMPL+H и файлы `.pkl`.
Загружайте через карточку «Модель SMPL-X» в «Модели и инструменты».

## Blender

Нажмите «Установить всё рекомендуемое» или «Установить» в карточке Blender — ставится Blender 4.5.
Уже установленный Blender можно указать в «Настройках», например
`C:\Program Files\Blender Foundation\Blender 4.5\blender.exe` (Mac: `/Applications/Blender.app`).

## Mac: Gatekeeper

Сборка не подписана Apple. Щелчок правой кнопкой (Control-щелчок) по `INSTALL.command` или приложению →
«Открыть» → «Открыть». Если не помогло: «Системные настройки» → «Конфиденциальность и безопасность» →
«Всё равно открыть».

## Mac: Command Line Tools

```bash
xcode-select --install
```

## Как повторить прерванную установку

Запустите INSTALL.cmd (Mac: INSTALL.command) или нажмите «Установить всё рекомендуемое» ещё раз.
Готовые компоненты сохраняются, загрузки продолжаются с места обрыва, недокачанные файлы
не считаются установленными. После установки WSL и перезагрузки — тоже просто нажмите кнопку снова.

## Отчёт для поддержки

«Модели и инструменты» → **«Отчёт для поддержки»**: файл с проверкой компьютера, версиями и журналами
установки (без видео и анимаций) сохраняется в «Загрузки». Перед отправкой его можно открыть и просмотреть —
в путях есть имя пользователя Windows. Если Studio не запускается, приложите журналы:

- Windows: `%LOCALAPPDATA%\MoCapGate Studio\logs\install-*.log`
- Mac: `~/Library/Logs/MoCapGate/install-*.log`

и результат проверки из папки приложения:

```powershell
cd "$env:LOCALAPPDATA\MoCapGate Studio\mocapgate"
.\python\python.exe mocapgate.py preflight --json | Out-File -Encoding utf8 "$env:USERPROFILE\Downloads\mocapgate-check.json"
.\python\python.exe mocapgate.py doctor
```

Mac:

```bash
cd ~/Applications/"MoCapGate Studio.app"/Contents/Resources/mocapgate
./python/bin/python3.12 mocapgate.py preflight --json > ~/Downloads/mocapgate-check.json
```

## GEM-X: «процесс остановлен системой», нехватка памяти, 4K с телефона

1. В настройках дубля: «Разрешение для распознавания» — 1280; «Обработка частями» — «Авто» или 15–30 с; режим «Быстро (ONNX)».
2. «Модели и инструменты» → «Тест производительности» — покажет пик видеопамяти и ОЗУ и предложит настройки
   («Применить для новых дублей»). Во время обработки под полосой видно текущую видеопамять и ОЗУ WSL.
3. Выделите WSL больше памяти (кнопка в «Проверить компьютер» или `.wslconfig`).

`Warp … insufficient CUDA driver version` — Warp собран под CUDA 13 и работает на процессоре. Обновите драйвер NVIDIA
до 580+ или переустановите GEM-X: установщик ставит Warp для CUDA 12. Сама по себе эта строка не причина сбоя.

`IndexError: list index out of range` в `device_from_torch` / `AlignVectorsWarp` — Warp не видит видеокарту (собран под
CUDA 13, а драйвер — CUDA 12). С 0.3.3-beta.6 GEM-X в этом случае не падает, а считает эту часть на процессоре. Для полной
скорости: переустановите GEM-X (поставится Warp для CUDA 12) или обновите драйвер NVIDIA до 580+.
