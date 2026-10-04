# Run from the downloaded package. No administrator rights required.
[CmdletBinding()]
param(
    [string]$InstallerPath,
    [switch]$FullAvatar,
    [string]$SmplxModel,
    [switch]$SkipLaunch,
    [switch]$SkipAI,
    [switch]$Portable,
    [switch]$Plan
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$runtimeRoot = Join-Path $env:LOCALAPPDATA 'MoCapGate Runtime'
$userBin = Join-Path $env:USERPROFILE '.local/bin'
if ($FullAvatar -and (!(Test-Path -LiteralPath $SmplxModel -PathType Leaf))) {
    throw 'FullAvatar requires -SmplxModel pointing to your licensed SMPLX_NEUTRAL.npz download.'
}
if ($InstallerPath -and !(Test-Path -LiteralPath $InstallerPath -PathType Leaf)) { throw 'Installer not found.' }
if ($Plan) {
    Write-Output 'Install uv from astral.sh if missing; Python 3.12 and numpy in a per-user venv; MediaPipe and its models.'
    Write-Output ('Runtime: '+$runtimeRoot)
    if ($FullAvatar) { Write-Output 'Install isolated CPU torch/smplx and connect the supplied licensed model. Local GVHMR remains a separate NVIDIA setup.' }
    return
}
$env:PATH = $userBin + ';' + $env:PATH
$uvCommand = Get-Command uv -ErrorAction SilentlyContinue
if (!$uvCommand) {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    $env:UV_INSTALL_DIR = $userBin
    $officialInstaller = Invoke-RestMethod 'https://astral.sh/uv/install.ps1'
    Invoke-Expression $officialInstaller
    $uvCommand = Get-Command uv -ErrorAction Stop
}
$uvExe = $uvCommand.Source
function Invoke-Checked([string]$Program, [string[]]$Arguments) {
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) { throw ('Command failed: '+$Program+' (exit '+$LASTEXITCODE+')') }
}
$runtimePython = Join-Path $runtimeRoot 'Scripts/python.exe'
if (!(Test-Path -LiteralPath $runtimePython)) {
    Invoke-Checked $uvExe @('python','install','3.12')
    Invoke-Checked $uvExe @('venv','--python','3.12',$runtimeRoot)
}
Invoke-Checked $uvExe @('pip','install','--python',$runtimePython,'numpy==1.26.4','imageio-ffmpeg==0.6.0')
$env:PYTHONUTF8 = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:MOCAPGATE_PYTHON = $runtimePython
if ($InstallerPath) {
    $installer = Start-Process -FilePath (Resolve-Path -LiteralPath $InstallerPath).Path -ArgumentList '/S' -Wait -PassThru -WindowStyle Hidden
    if ($installer.ExitCode -ne 0) { throw ('Installer failed: '+$installer.ExitCode) }
}
$installedRoot = Join-Path $env:LOCALAPPDATA 'MoCapGate Studio/mocapgate'
$appRoot = if (!$Portable -and (Test-Path -LiteralPath (Join-Path $installedRoot 'mocapgate.py'))) { $installedRoot } else { $projectRoot }
$entry = Join-Path $appRoot 'mocapgate.py'
if (!(Test-Path -LiteralPath $entry)) { throw 'Run this script from the MoCapGate portable package or repository.' }
Invoke-Checked $runtimePython @((Join-Path $PSScriptRoot 'install_ffmpeg.py'))
Invoke-Checked $runtimePython @((Join-Path $PSScriptRoot 'install_example.py'),$appRoot)
if (!$SkipAI) {
    Invoke-Checked $runtimePython @($entry,'setup','mediapipe','--model','heavy')
    Invoke-Checked $runtimePython @((Join-Path $PSScriptRoot 'prepare_models.py'),$appRoot)
}
if ($FullAvatar) {
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
if (!$Portable) { [Environment]::SetEnvironmentVariable('MOCAPGATE_PYTHON',$runtimePython,'User') }
Invoke-Checked $runtimePython @($entry,'doctor')
Write-Output 'Setup complete: Python, FFmpeg, MediaPipe and a playable two-person sample. Blender for FBX and NVIDIA GVHMR are separate components.'
if (!$SkipLaunch) {
    $desktopExe = Join-Path $env:LOCALAPPDATA 'MoCapGate Studio/mocapgate-studio.exe'
    if (!$Portable -and (Test-Path -LiteralPath $desktopExe)) { Start-Process -FilePath $desktopExe }
    else { Invoke-Checked $runtimePython @($entry,'studio') }
}
