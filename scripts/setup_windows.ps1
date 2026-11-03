# MoCapGate Studio per-user setup. Run from the complete, extracted package
# (INSTALL.cmd or scripts\start_windows.cmd). No administrator rights required.
# This file is saved as UTF-8 with BOM so Windows PowerShell 5.1 reads the Russian text correctly.
#
# Exit codes: 0 done, 1 a setup step failed, 3 MoCapGate Studio is running,
# 4 package not extracted / incomplete, 5 not enough disk space, 6 unsupported Windows/PowerShell.
# -CheckOnly runs the system checks and `mocapgate.py preflight` without installing anything.
# Log: %LOCALAPPDATA%\MoCapGate Studio\logs\install-<timestamp>.log
[CmdletBinding()]
param(
    [string]$InstallerPath,
    [switch]$FullAvatar,
    [string]$SmplxModel,
    [switch]$SkipLaunch,
    [switch]$SkipAI,
    [switch]$Portable,
    [switch]$Plan,
    [switch]$CheckOnly
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$runtimeRoot = Join-Path $env:LOCALAPPDATA 'MoCapGate Runtime'
$userBin = Join-Path $env:USERPROFILE '.local/bin'
$installedRoot = Join-Path $env:LOCALAPPDATA 'MoCapGate Studio/mocapgate'
$troubleshootingRu = Join-Path $projectRoot 'docs\troubleshooting.ru.md'
$troubleshootingEn = Join-Path $projectRoot 'docs\troubleshooting.en.md'
$minimumFreeGB = 5
$recommendedFreeGB = 50
if ($FullAvatar -and (!(Test-Path -LiteralPath $SmplxModel -PathType Leaf))) {
    throw 'FullAvatar requires -SmplxModel pointing to your licensed SMPLX_NEUTRAL.npz download.'
}
if ($InstallerPath -and !(Test-Path -LiteralPath $InstallerPath -PathType Leaf)) { throw 'Installer not found.' }
if ($Plan) {
    Write-Output 'Install the supplied EXE; use bundled Python/uv for native packages; prepare FFmpeg, FFprobe, Blender and optional MediaPipe models. Legacy source packages use an isolated Python runtime.'
    Write-Output ('Runtime: '+$runtimeRoot)
    if ($FullAvatar) { Write-Output 'Install isolated CPU torch/smplx and connect the supplied licensed model. Local GVHMR remains a separate NVIDIA setup.' }
    return
}

# --- helpers -----------------------------------------------------------------
$script:step = 'Подготовка / Preparing'
$script:stopCode = 0
function Set-Step([string]$Name) {
    $script:step = $Name
    Write-Host ''
    Write-Host ('==> '+$Name) -ForegroundColor Cyan
}
function Write-Warn([string]$Ru, [string]$En) {
    Write-Host ('[!] '+$Ru) -ForegroundColor Yellow
    Write-Host ('    '+$En) -ForegroundColor Yellow
}
function Stop-Setup([int]$Code, [string]$Ru, [string]$En) {
    $script:stopCode = $Code
    Write-Host ''
    Write-Host ('[X] '+$Ru) -ForegroundColor Red
    Write-Host ('    '+$En) -ForegroundColor Red
    throw 'MOCAPGATE_SETUP_STOPPED'
}
# Runs a program, shows its output (also in the log) and fails on a non-zero exit code.
function Invoke-Checked([string]$Program, [string[]]$Arguments) {
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        & $Program @Arguments 2>&1 | ForEach-Object {
            if ($_ -is [System.Management.Automation.ErrorRecord]) { Write-Host $_.ToString() } else { Write-Host ([string]$_) }
        }
        $code = $LASTEXITCODE
    } finally { $ErrorActionPreference = $previous }
    if ($code -ne 0) { throw ('Command failed: '+$Program+' (exit '+$code+')') }
}
function Test-StudioRunning {
    if (Get-Process -Name 'mocapgate-studio' -ErrorAction SilentlyContinue) { return $true }
    try {
        $servers = @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction Stop |
            Where-Object { $_.CommandLine -and $_.CommandLine -like '*mocapgate.py*studio*' })
        return $servers.Count -gt 0
    } catch { return $false }
}
function Test-Prerequisites([bool]$Strict) {
    if (![Environment]::Is64BitOperatingSystem) {
        Stop-Setup 6 'Нужна 64-битная Windows 10/11 (x64). Эта система 32-битная.' 'A 64-bit Windows 10/11 (x64) is required. This system is 32-bit.'
    }
    $psVersion = $PSVersionTable.PSVersion
    if ($psVersion.Major -lt 5 -or ($psVersion.Major -eq 5 -and $psVersion.Minor -lt 1)) {
        Stop-Setup 6 ('Нужен Windows PowerShell 5.1 или новее (сейчас '+$PSVersionTable.PSVersion+'). Обновите Windows.') ('Windows PowerShell 5.1 or newer is required (found '+$PSVersionTable.PSVersion+'). Update Windows.')
    }
    $build = [Environment]::OSVersion.Version.Build
    Write-Host ('Windows build '+$build+', PowerShell '+$PSVersionTable.PSVersion+', 64-bit process: '+[Environment]::Is64BitProcess)
    if ($build -lt 19044) {
        Write-Warn 'Рекомендуется Windows 10 21H2 (сборка 19044) или Windows 11: на старых сборках WSL2 для GEM-X/GVHMR может не работать.' 'Windows 10 21H2 (build 19044) or Windows 11 is recommended: WSL2 for GEM-X/GVHMR may not work on older builds.'
    }
    # Explorer runs a script opened inside a ZIP from a temporary folder such as
    # %TEMP%\Temp1_MoCapGate.zip\ - the rest of the package is missing there.
    $tempRoot = if ($env:TEMP) { [IO.Path]::GetFullPath($env:TEMP).TrimEnd('\') + '\' } else { '' }
    $insideZip = ($projectRoot -match '\.zip(\\|/|$)') -or ($projectRoot -like '*\AppData\Local\Temp\*') -or ($tempRoot -and $projectRoot.StartsWith($tempRoot, [StringComparison]::OrdinalIgnoreCase))
    if ($insideZip) {
        Stop-Setup 4 ('Пакет запущен из ZIP или временной папки: '+$projectRoot+'. Нажмите на архив правой кнопкой → «Извлечь все…», выберите обычную папку (например, Загрузки) и запустите INSTALL.cmd из распакованной папки.') ('The package runs from inside a ZIP or a temporary folder: '+$projectRoot+'. Right-click the archive → "Extract All…", choose a normal folder (e.g. Downloads) and run INSTALL.cmd from the extracted folder.')
    }
    $required = @('mocapgate.py','core','scripts\install_example.py','scripts\prepare_models.py','scripts\install_ffmpeg.py')
    if (Test-Path -LiteralPath (Join-Path $projectRoot 'native-manifest.json')) { $required += @('python\python.exe','uv.exe') }
    $missing = @($required | Where-Object { !(Test-Path -LiteralPath (Join-Path $projectRoot $_)) })
    if ($missing.Count -gt 0) {
        Stop-Setup 4 ('Пакет распакован не полностью, нет: '+($missing -join ', ')+'. Распакуйте архив заново целиком («Извлечь все…») и проверьте, не удалил ли антивирус файлы.') ('The package is incomplete, missing: '+($missing -join ', ')+'. Extract the whole archive again ("Extract All…") and check that antivirus did not remove files.')
    }
    if ($projectRoot.Length -gt 120) {
        $longPaths = $null
        try { $longPaths = (Get-ItemProperty -LiteralPath 'HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem' -Name LongPathsEnabled -ErrorAction Stop).LongPathsEnabled } catch { }
        if ($longPaths -ne 1) {
            Write-Warn ('Длинный путь к пакету ('+$projectRoot.Length+' символов) и выключены длинные пути Windows. Перенесите папку ближе к корню, например C:\MoCapGate. См. troubleshooting.ru.md → «Слишком длинный путь».') ('Long package path ('+$projectRoot.Length+' characters) and Windows long paths are disabled. Move the folder closer to the drive root, e.g. C:\MoCapGate. See troubleshooting.en.md → "Path too long".')
        }
    }
    if ($env:OneDrive -and $projectRoot.StartsWith($env:OneDrive, [StringComparison]::OrdinalIgnoreCase)) {
        Write-Warn 'Пакет лежит в папке OneDrive: синхронизация может блокировать или выгружать файлы. Лучше распаковать в C:\MoCapGate или «Загрузки» вне OneDrive.' 'The package is inside OneDrive: syncing can lock or offload files. Prefer C:\MoCapGate or a Downloads folder outside OneDrive.'
    }
    $documents = [Environment]::GetFolderPath('MyDocuments')
    if ($env:OneDrive -and $documents -and $documents.StartsWith($env:OneDrive, [StringComparison]::OrdinalIgnoreCase)) {
        Write-Warn ('«Документы» синхронизируются OneDrive ('+$documents+'): библиотека дублей «MoCapGate Takes» будет занимать место в облаке. Папку библиотеки можно сменить в «Настройках».') ('"Documents" is synced by OneDrive ('+$documents+'): the "MoCapGate Takes" library will use cloud space. You can change the library folder in Settings.')
    }
    $drive = [IO.Path]::GetPathRoot($env:LOCALAPPDATA)
    try { $freeBytes = (New-Object IO.DriveInfo($drive)).AvailableFreeSpace } catch { $freeBytes = $null }
    if ($null -ne $freeBytes) {
        $freeGB = [Math]::Floor($freeBytes / 1GB)
        Write-Host ('Свободно на диске / Free space on '+$drive+': '+$freeGB+' GB')
        if ($freeGB -lt $minimumFreeGB) {
            if ($Strict) { Stop-Setup 5 ('На диске '+$drive+' свободно '+$freeGB+' ГБ, нужно не меньше '+$minimumFreeGB+' ГБ. Освободите место и запустите установку снова.') ('Only '+$freeGB+' GB free on '+$drive+', at least '+$minimumFreeGB+' GB is required. Free up space and run setup again.') }
            Write-Warn ('Свободно меньше '+$minimumFreeGB+' ГБ — установка не начнётся.') ('Less than '+$minimumFreeGB+' GB free — setup will not start.')
        } elseif ($freeGB -lt $recommendedFreeGB) {
            Write-Warn ('Для всех моделей (GEM-X ~30 ГБ, GVHMR ~15 ГБ) рекомендуется '+$recommendedFreeGB+' ГБ свободного места; базовый набор поместится.') ('About '+$recommendedFreeGB+' GB free is recommended for all models (GEM-X ~30 GB, GVHMR ~15 GB); the basic set fits.')
        }
    }
    if (Test-StudioRunning) {
        if ($Strict) { Stop-Setup 3 'MoCapGate Studio сейчас запущен. Закройте окно приложения (и консоль Studio, если она открыта), затем запустите установку снова.' 'MoCapGate Studio is running. Close the app window (and the Studio console if open), then run setup again.' }
        Write-Warn 'MoCapGate Studio запущен — перед установкой его нужно закрыть.' 'MoCapGate Studio is running — close it before installing.'
    }
}
# Runs `mocapgate.py preflight --json` if this version has it and prints a short summary.
# Returns its exit code (0 no blockers, 2 blockers) or $null when the command is unavailable.
function Invoke-Preflight([string]$Python, [string]$AppRoot, [bool]$Network) {
    $unavailable = 'Проверка компьютера недоступна в этой версии. / Computer check is not available in this version.'
    $hasModule = @(Get-ChildItem -LiteralPath (Join-Path $AppRoot 'core') -Filter 'preflight*' -ErrorAction SilentlyContinue).Count -gt 0
    if (!$hasModule) { Write-Host $unavailable; return $null }
    $arguments = @((Join-Path $AppRoot 'mocapgate.py'), 'preflight', '--json')
    if (!$Network) { $arguments += '--no-network' }
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $items = @(& $Python @arguments 2>&1)
        $code = $LASTEXITCODE
    } catch {
        $items = @($_.ToString()); $code = -1
    } finally { $ErrorActionPreference = $previous }
    $stdout = @($items | Where-Object { $_ -isnot [System.Management.Automation.ErrorRecord] } | ForEach-Object { [string]$_ })
    $stderr = @($items | Where-Object { $_ -is [System.Management.Automation.ErrorRecord] } | ForEach-Object { $_.ToString() })
    if ((($stdout + $stderr) -join "`n") -match 'invalid choice|unrecognized arguments') { Write-Host $unavailable; return $null }
    $report = $null
    try { $report = ($stdout -join "`n") | ConvertFrom-Json } catch { $report = $null }
    if ($null -eq $report -or $null -eq $report.checks) {
        ($stdout + $stderr) | ForEach-Object { Write-Host $_ }
        return $code
    }
    $lang = if ((Get-UICulture).TwoLetterISOLanguageName -eq 'ru') { 'ru' } else { 'en' }
    function Get-Text($Value) {
        if ($null -eq $Value) { return '' }
        if ($Value -is [string]) { return $Value }
        if ($Value.$lang) { return [string]$Value.$lang }
        return [string]$Value.en
    }
    foreach ($check in $report.checks) {
        $mark = switch ($check.level) { 'ok' { '[OK]' } 'warn' { '[!] ' } 'fail' { '[X] ' } default { '[i] ' } }
        $color = switch ($check.level) { 'ok' { 'Green' } 'warn' { 'Yellow' } 'fail' { 'Red' } default { 'Gray' } }
        Write-Host ($mark+' '+(Get-Text $check.title)) -ForegroundColor $color
        if ($check.level -eq 'warn' -or $check.level -eq 'fail') {
            $detail = Get-Text $check.detail
            if ($detail) { Write-Host ('      '+$detail) }
            if ($check.fix) {
                $label = Get-Text $check.fix.label
                $value = if ($check.fix.kind -eq 'action') { 'MoCapGate Studio → «Модели и инструменты» / Models & tools' } else { [string]$check.fix.value }
                if ($label -or $value) { Write-Host ('      -> '+((@($label, $value) | Where-Object { $_ }) -join ': ')) }
            }
        }
    }
    if ($report.recommend) {
        $models = @($report.recommend.models) -join ', '
        $reason = Get-Text $report.recommend.reason
        if ($models -or $reason) { Write-Host ('Рекомендуемые модели / Recommended models: '+$models+$(if ($reason) { ' — '+$reason } else { '' })) }
    }
    return $code
}

# --- log ---------------------------------------------------------------------
$logPath = $null
try {
    $logDir = Join-Path $env:LOCALAPPDATA 'MoCapGate Studio\logs'
    New-Item -ItemType Directory -Force -Path $logDir | Out-Null
    $prefix = if ($CheckOnly) { 'check-' } else { 'install-' }
    $logPath = Join-Path $logDir ($prefix+(Get-Date -Format 'yyyyMMdd-HHmmss')+'.log')
    Start-Transcript -LiteralPath $logPath | Out-Null
} catch { $logPath = $null }

$exitCode = 0
try {
    try { [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch { }
    # Older Windows PowerShell defaults can lack TLS 1.2, which the download servers require.
    [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
    $env:PYTHONUTF8 = '1'
    $env:PYTHONUNBUFFERED = '1'
    $env:PYTHONDONTWRITEBYTECODE = '1'

    Set-Step 'Проверка системы и пакета / Checking system and package'
    Test-Prerequisites (!$CheckOnly)

    if ($CheckOnly) {
        Set-Step 'Проверка компьютера / Computer check'
        $checkRoot = $null; $checkPython = $null
        foreach ($candidate in @($projectRoot, $installedRoot)) {
            $python = Join-Path $candidate 'python/python.exe'
            if ((Test-Path -LiteralPath (Join-Path $candidate 'mocapgate.py')) -and (Test-Path -LiteralPath $python)) { $checkRoot = $candidate; $checkPython = $python; break }
        }
        if (!$checkPython -and (Test-Path -LiteralPath (Join-Path $runtimeRoot 'Scripts/python.exe'))) { $checkRoot = $projectRoot; $checkPython = Join-Path $runtimeRoot 'Scripts/python.exe' }
        if (!$checkPython) {
            Write-Warn 'Не найден встроенный Python этого пакета — сначала запустите INSTALL.cmd.' 'The bundled Python was not found — run INSTALL.cmd first.'
        } else {
            $result = Invoke-Preflight $checkPython $checkRoot $true
            if ($result -eq 2) { $exitCode = 2 }
        }
    } else {
        $env:PATH = $userBin + ';' + $env:PATH
        if ($InstallerPath) {
            Set-Step 'Установка приложения MoCapGate Studio / Installing MoCapGate Studio'
            $installer = Start-Process -FilePath (Resolve-Path -LiteralPath $InstallerPath).Path -ArgumentList '/S' -Wait -PassThru -WindowStyle Hidden
            if ($installer.ExitCode -ne 0) { throw ('Installer failed: '+$installer.ExitCode) }
        }
        $appRoot = if (!$Portable -and (Test-Path -LiteralPath (Join-Path $installedRoot 'mocapgate.py'))) { $installedRoot } else { $projectRoot }
        $entry = Join-Path $appRoot 'mocapgate.py'
        if (!(Test-Path -LiteralPath $entry)) { throw 'Run this script from the complete MoCapGate package.' }
        $nativePackage = Test-Path -LiteralPath (Join-Path $appRoot 'native-manifest.json')
        Set-Step 'Подготовка Python / Preparing Python'
        if ($nativePackage) {
            $runtimePython = Join-Path $appRoot 'python/python.exe'
            $uvExe = Join-Path $appRoot 'uv.exe'
            if (!(Test-Path -LiteralPath $runtimePython) -or !(Test-Path -LiteralPath $uvExe)) { throw 'Incomplete native package: bundled Python/uv missing. Extract the complete ZIP or reinstall the EXE.' }
            Invoke-Checked $runtimePython @('-c', 'import sys; assert sys.version_info[:3] == (3,12,13), "Native Studio requires bundled CPython 3.12.13"')
            $env:PATH = $appRoot + ';' + $env:PATH
        } else {
            $uvCommand = Get-Command uv -ErrorAction SilentlyContinue
            if (!$uvCommand) {
                $env:UV_INSTALL_DIR = $userBin
                $officialInstaller = Invoke-RestMethod 'https://astral.sh/uv/install.ps1'
                Invoke-Expression $officialInstaller
                $uvCommand = Get-Command uv -ErrorAction Stop
            }
            $uvExe = $uvCommand.Source
            $runtimePython = Join-Path $runtimeRoot 'Scripts/python.exe'
            if (!(Test-Path -LiteralPath $runtimePython)) {
                Invoke-Checked $uvExe @('python','install','3.12')
                Invoke-Checked $uvExe @('venv','--python','3.12',$runtimeRoot)
            }
            Invoke-Checked $uvExe @('pip','install','--python',$runtimePython,'numpy==1.26.4','imageio-ffmpeg==0.6.0')
        }
        $env:MOCAPGATE_PYTHON = $runtimePython
        Set-Step 'FFmpeg, Blender и базовые инструменты / FFmpeg, Blender and basic tools'
        if ($nativePackage) { Invoke-Checked $runtimePython @($entry,'setup','recommended') }
        else { Invoke-Checked $runtimePython @((Join-Path $PSScriptRoot 'install_ffmpeg.py')) }
        Set-Step 'Демо-дубль Sports2D / Sports2D demo take'
        Invoke-Checked $runtimePython @((Join-Path $PSScriptRoot 'install_example.py'),$appRoot)
        if (!$SkipAI) {
            Set-Step 'MediaPipe и модели людей, кистей и лица / MediaPipe and person, hand and face models'
            Invoke-Checked $runtimePython @($entry,'setup','mediapipe','--model','heavy')
            Invoke-Checked $runtimePython @((Join-Path $PSScriptRoot 'prepare_models.py'),$appRoot)
        }
        if ($FullAvatar) {
            Set-Step 'Инструменты SMPL-X / SMPL-X tools'
            $surfaceRoot = Join-Path $env:LOCALAPPDATA 'MoCapGate SMPL-X'
            $surfacePython = Join-Path $surfaceRoot 'Scripts/python.exe'
            if (!(Test-Path -LiteralPath $surfacePython)) { Invoke-Checked $uvExe @('venv','--python','3.12',$surfaceRoot) }
            Invoke-Checked $uvExe @('pip','install','--python',$surfacePython,'torch==2.3.0','--index-url','https://download.pytorch.org/whl/cpu')
            Invoke-Checked $uvExe @('pip','install','--python',$surfacePython,'smplx==0.1.28','numpy==1.26.4')
            $env:MOCAPGATE_SETUP_MODEL = (Resolve-Path -LiteralPath $SmplxModel).Path
            $env:MOCAPGATE_SETUP_SURFACE_PYTHON = $surfacePython
            Push-Location $appRoot
            try {
                Invoke-Checked $runtimePython @((Join-Path $PSScriptRoot 'configure_surface.py'),$appRoot)
            } finally { Pop-Location }
        }
        if (!$Portable -and !$nativePackage) { [Environment]::SetEnvironmentVariable('MOCAPGATE_PYTHON',$runtimePython,'User') }
        Set-Step 'Итоговая проверка / Final check'
        Invoke-Checked $runtimePython @($entry,'doctor')
        Set-Step 'Проверка компьютера / Computer check'
        # Offline mode: setup itself does not contact extra servers. Warnings do not fail the install.
        $preflight = Invoke-Preflight $runtimePython $appRoot $false
        if ($preflight -eq 2) {
            Write-Warn 'Установка завершена, но для части моделей компьютер не готов (см. [X] выше). Базовые функции работают; подробности — «Модели и инструменты» → «Проверить компьютер».' 'Setup finished, but the computer is not ready for some models (see [X] above). Basic features work; details: Models & tools → Check the computer.'
        }
        Write-Host ''
        Write-Host 'Готово: приложение, инструменты и демо-дубль установлены. Модели для NVIDIA (GEM-X, GVHMR) и SMPL-X устанавливаются в Studio: «Модели и инструменты».' -ForegroundColor Green
        Write-Output 'Setup complete: runtime, tools and playable two-person sample. NVIDIA backends and licensed body/character models are configured separately.'
        if (!$SkipLaunch) {
            Set-Step 'Запуск MoCapGate Studio / Starting MoCapGate Studio'
            $desktopExe = Join-Path $env:LOCALAPPDATA 'MoCapGate Studio/mocapgate-studio.exe'
            if (!$Portable -and (Test-Path -LiteralPath $desktopExe)) { Start-Process -FilePath $desktopExe }
            else { Invoke-Checked $runtimePython @($entry,'studio') }
        }
    }
} catch {
    Write-Host ''
    if ($script:stopCode) {
        $exitCode = $script:stopCode
    } else {
        $exitCode = 1
        Write-Host ('[X] Ошибка на шаге: '+$script:step) -ForegroundColor Red
        Write-Host ('    Setup failed at step: '+$script:step) -ForegroundColor Red
        Write-Host ('    Причина / Reason: '+$_.Exception.Message) -ForegroundColor Red
        Write-Host 'Запустите INSTALL.cmd ещё раз: готовые компоненты сохраняются, загрузки продолжаются с места обрыва.'
        Write-Host 'Run INSTALL.cmd again: finished components are kept and downloads resume where they stopped.'
    }
    if ($logPath) { Write-Host ('Журнал / Log: '+$logPath) }
    Write-Host ('Решение частых проблем: '+$troubleshootingRu)
    Write-Host ('Troubleshooting: '+$troubleshootingEn)
} finally {
    if ($logPath) { try { Stop-Transcript | Out-Null } catch { } }
}
exit $exitCode
