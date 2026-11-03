# Installation troubleshooting

[Русская версия](troubleshooting.ru.md) · [Installation](install.en.md)

First: **Models & tools → Check the computer** (or `CHECK-COMPUTER.cmd` from the quickstart).
Most problems show up there right away, with a fix button or command.
Commands marked **(administrator)** run in PowerShell opened via right-click on Start →
"Terminal (Admin)" / "Windows PowerShell (Admin)". All others run in a normal PowerShell.
MoCapGate does not run these commands for you.

## Quick table

| Symptom / message | Cause | What to do |
|---|---|---|
| "Windows protected your PC" | The build is not code-signed (SmartScreen does not know the publisher) | [SmartScreen](#smartscreen) |
| "The archive is not extracted…", code 4, `mocapgate.py` / `python\python.exe` missing | Run from inside the ZIP or extraction incomplete | [Archive](#archive-not-fully-extracted) |
| `path too long`, `FileNotFoundError` on a long path | Path longer than 260 characters | [Long paths](#path-too-long) |
| Files disappear, "cloud file not available", slow | Folder is in OneDrive | [OneDrive](#onedrive) |
| Files removed after extraction, `Access is denied`, `CERTIFICATE_VERIFY_FAILED` | Antivirus blocks files or scans HTTPS | [Antivirus](#antivirus) |
| `timed out`, `Name or service not known`, `ProxyError`, 407 | No internet or a proxy is required | [Internet and proxy](#internet-and-proxy) |
| `0x80370102`, `0x8007019e`, `WSL 1`, Ubuntu "Installing", WSL hangs | WSL problems | [WSL](#wsl) |
| `Could not get lock /var/lib/dpkg/lock-frontend` | Another update is running in Ubuntu | [apt lock](#apt-is-busy) |
| `No space left on device`, "at least … GB is needed", code 5 | Not enough disk space | [Disk](#disk-full) |
| "Driver …: CUDA 12 needs 535 or newer", `CUDA driver version is insufficient` | Old NVIDIA driver | [Driver](#nvidia-driver) |
| `CUDA out of memory`, `Killed`, process ends without an error | Not enough VRAM or WSL memory | [Memory](#out-of-memory) |
| "RTX 50 series is not supported" (GVHMR) | GVHMR is built on PyTorch 2.3 / CUDA 12.1 | [RTX 50](#rtx-50-and-gvhmr) |
| "Invalid SMPL-X file", `SMPLX_NEUTRAL.npz` not found | Wrong file selected | [SMPL-X](#smpl-x) |
| "Blender is required for FBX", Blender not found | Blender not installed or not detected | [Blender](#blender) |
| "Studio is running", code 3 | The app is open during setup | Close MoCapGate Studio and run INSTALL.cmd again |
| Mac: "cannot be opened because the developer cannot be verified" | Gatekeeper, unsigned build | [Mac](#mac-gatekeeper) |
| Mac: `xcrun: error: invalid active developer path` | Command Line Tools missing | [Mac](#mac-command-line-tools) |
| Setup was interrupted | Network drop, restart, cancel | [Retry](#retrying-an-interrupted-install) |

INSTALL.cmd / setup exit codes: `0` done, `1` a step failed (see the message and log), `3` Studio is running,
`4` archive not extracted or incomplete, `5` not enough space, `6` not 64-bit Windows or old PowerShell.

## SmartScreen

MoCapGate builds are not signed with a paid certificate, so Windows shows a warning. It is not a virus scan
result. If the archive came from the [releases page](https://github.com/MaverickGH/app-releases/releases):
"More info" → "Run anyway". You can also clear the "downloaded from the internet" mark on the archive **before** extracting:

```powershell
Unblock-File -Path "$env:USERPROFILE\Downloads\MoCapGate-*-quickstart.zip"
```

## Archive not fully extracted

Double-clicking a file inside a ZIP runs it from a temporary folder without the other files.
Right-click the ZIP → "Extract All…" → e.g. `C:\MoCapGate`, then run INSTALL.cmd from that folder. Or in PowerShell:

```powershell
Expand-Archive -Path "$env:USERPROFILE\Downloads\MoCapGate-*-quickstart.zip" -DestinationPath C:\MoCapGate -Force
```

If files are still missing after extraction, antivirus removed them (see below).

## Path too long

Extract closer to the drive root (`C:\MoCapGate`). Or enable Windows long paths **(administrator)**, then sign out and in:

```powershell
New-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" -Name "LongPathsEnabled" -Value 1 -PropertyType DWORD -Force
```

## OneDrive

Do not extract the package into OneDrive. If "Documents" is synced, the takes library
`Documents\MoCapGate Takes` goes to the cloud too: change the library folder in Settings
(e.g. `C:\MoCapGate Takes`) or set it to "Always keep on this device" in OneDrive.

## Antivirus

Add exclusions for the app, component and takes folders. For Microsoft Defender **(administrator)**:

```powershell
Add-MpPreference -ExclusionPath "$env:LOCALAPPDATA\MoCapGate Studio"
Add-MpPreference -ExclusionPath "$env:USERPROFILE\.cache\mocapgate"
Add-MpPreference -ExclusionPath "$env:USERPROFILE\Documents\MoCapGate Takes"
```

Do this only for a package from the releases page. For other antivirus products use the same folders in their settings.
`CERTIFICATE_VERIFY_FAILED` / `SSL: certificate verify failed` usually means the antivirus inspects HTTPS traffic
("web protection", "HTTPS/SSL scanning"). Turn that feature off for the duration of setup, or exclude `python.exe`
and `uv.exe` from `%LOCALAPPDATA%\MoCapGate Studio\mocapgate` from web protection, then install again.

## Internet and proxy

Check access to the download servers:

```powershell
Test-NetConnection github.com -Port 443
curl.exe -I https://huggingface.co
curl.exe -I https://download.blender.org
```

If your network works only through a proxy, set it for your account and restart Studio
(address and port come from your administrator):

```powershell
setx HTTPS_PROXY http://proxy.example:3128
setx HTTP_PROXY http://proxy.example:3128
```

For WSL on Windows 11 22H2+ you can inherit the Windows network settings in `%USERPROFILE%\.wslconfig`:

```ini
[wsl2]
networkingMode=mirrored
autoProxy=true
```

then `wsl --shutdown`. A VPN that blocks WSL is best disabled during setup.

## WSL

| Message | What to do |
|---|---|
| `0x80370102` | Enable **Intel VT-x / AMD SVM** virtualization in BIOS/UEFI; check: Task Manager → Performance → CPU → "Virtualization". Then enable the feature **(administrator)**: `dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart` and restart |
| `0x8007019e`, `WSL_E_WSL_OPTIONAL_COMPONENT_REQUIRED` | The WSL feature is off **(administrator)**: `dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart`, restart |
| "WSL 2 requires an update to its kernel component", `0x800701bc`, old WSL | `wsl --update` (Windows may ask for administrator approval) |
| Ubuntu stays `Installing` | Open "Ubuntu" from the Start menu and finish creating the user. Check: `wsl -l -v` |
| `VERSION 1` in `wsl -l -v` | `wsl --set-version Ubuntu 2` and `wsl --set-default-version 2` |
| WSL does not respond, setup hangs | `wsl --shutdown`, then Install everything recommended again |

Useful commands:

```powershell
wsl --status
wsl -l -v
wsl --update
wsl --shutdown
wsl --set-version Ubuntu 2
```

If a distribution is broken, install another one without touching the old: `wsl --install -d Ubuntu-24.04`,
then enter its name in Settings → Preferences and advanced paths → Advanced GVHMR paths → Runtime → WSL.
Rare Windows servicing errors (`0x800f0922`, features rolling back) — see [GVHMR install recovery](gvhmr-install-recovery.en.md).

## apt is busy

`Could not get lock /var/lib/dpkg/lock-frontend` — Ubuntu is running automatic updates. The installer waits up to
10 minutes. If that does not help, see what is running and repair an interrupted package install:

```powershell
wsl -d Ubuntu -u root -- bash -c "ps aux | grep -E 'apt|dpkg' | grep -v grep"
wsl -d Ubuntu -u root -- dpkg --configure -a
```

## Disk full

The basic setup needs 5 GB, GEM-X about 30 GB and GVHMR about 15 GB on the user profile drive (where the
Ubuntu disk lives as well). Check: `Get-PSDrive C`. Free up space (Disk Cleanup, "Delete old trash" in
MoCapGate) or move Ubuntu to another drive (recent WSL, after `wsl --update`):

```powershell
wsl --shutdown
wsl --manage Ubuntu --move D:\WSL\Ubuntu
```

## NVIDIA driver

Driver **535 or newer** is required. Check the version in Windows and inside WSL:

```powershell
nvidia-smi
wsl -d Ubuntu -- nvidia-smi
```

Install a current driver from [nvidia.com](https://www.nvidia.com/Download/index.aspx) or the NVIDIA App on
Windows. Do **not** install an NVIDIA driver inside Ubuntu — WSL uses the Windows driver.

## Out of memory

- `CUDA out of memory`: use a shorter or lower-resolution video, lower "How many people", close games and
  other GPU apps. GEM-X needs 8 GB of VRAM.
- `Killed`, or processing stops without a reason: by default WSL gets half of the RAM. Check the computer
  offers a "Give WSL N GB" button. Manually — the file `%USERPROFILE%\.wslconfig`:

```ini
[wsl2]
memory=16GB
swap=16GB
```

then `wsl --shutdown` and process again. Do not set more than your RAM minus 4 GB.

## RTX 50 and GVHMR

GVHMR runs on PyTorch 2.3 / CUDA 12.1, which does not support RTX 50 (Blackwell) cards.
Use **GEM-X** or **GVHMR · Colab** on them.

## SMPL-X

You need `SMPLX_NEUTRAL.npz` from the SMPL-X archive at [smpl-x.is.tue.mpg.de](https://smpl-x.is.tue.mpg.de/download.php)
(the downloaded ZIP itself is accepted). SMPL / SMPL+H models and `.pkl` files do not work.
Upload it with the SMPL-X model card in Models & tools.

## Blender

Click Install everything recommended or Install on the Blender card — Blender 4.5 is installed.
An existing Blender can be set in Settings, e.g.
`C:\Program Files\Blender Foundation\Blender 4.5\blender.exe` (Mac: `/Applications/Blender.app`).

## Mac: Gatekeeper

The build is not signed by Apple. Right-click (Control-click) `INSTALL.command` or the app → Open → Open.
If that does not help: System Settings → Privacy & Security → Open Anyway.

## Mac: Command Line Tools

```bash
xcode-select --install
```

## Retrying an interrupted install

Run INSTALL.cmd (Mac: INSTALL.command) or click Install everything recommended again. Finished components
are kept, downloads resume where they stopped, and partial files never count as installed. After WSL
installation and a restart, just click the button again.

## Support report

Models & tools → **Support report**: a file with the computer check, versions and install logs (no videos
or animations) is saved to Downloads. You can open and review it before sending — paths contain your
Windows user name. If Studio does not start, attach the logs:

- Windows: `%LOCALAPPDATA%\MoCapGate Studio\logs\install-*.log`
- Mac: `~/Library/Logs/MoCapGate/install-*.log`

and the check result from the app folder:

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

## GEM-X: “process stopped by the system”, out of memory, 4K phone video

1. Take settings: “Recognition resolution” 1280; “Process in parts” Auto or 15–30 s; mode “Fast (ONNX)”.
2. Models & tools → “Performance test” shows peak video memory and RAM and suggests settings (“Use for new takes”).
   While processing, current video memory and WSL RAM are shown under the progress bar.
3. Give WSL more memory (button in “Check the computer” or `.wslconfig`).

`Warp … insufficient CUDA driver version` — Warp is built for CUDA 13 and runs on the CPU. Update the NVIDIA driver to
580+ or reinstall GEM-X: setup installs a CUDA 12 Warp. This line alone is not the cause of a crash.

`IndexError: list index out of range` in `device_from_torch` / `AlignVectorsWarp` — Warp does not see the GPU (built for
CUDA 13, driver is CUDA 12). Since 0.3.3-beta.6 GEM-X no longer crashes here and runs this part on the CPU. For full
speed: reinstall GEM-X (installs the CUDA 12 Warp) or update the NVIDIA driver to 580+.
