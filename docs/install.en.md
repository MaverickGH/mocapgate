# Installing MoCapGate Studio

[Русская версия](install.md) · [Troubleshooting](troubleshooting.en.md)

Download a package from [MoCapGate releases](https://github.com/MaverickGH/app-releases/releases).
You do not need Git, Python, Node, Rust or a GitHub account: the package has its own Python 3.12.13 and uv.

## Requirements

| | Minimum | For NVIDIA models (GEM-X / GVHMR on this PC) |
|---|---|---|
| System | Windows 10 21H2 (build 19044) or Windows 11, x64 | same + WSL2 with Ubuntu (installed from the app) |
| Mac | macOS on Apple Silicon (an Intel build also exists) | GEM-X runs locally on Apple Silicon (ONNX/CoreML, ~14 GB, needs Command Line Tools); GVHMR via Colab only |
| Memory | 8 GB RAM | 16 GB recommended |
| Graphics | not required (GVHMR · Colab on any OS; GEM-X on Apple Silicon) | NVIDIA RTX with 8 GB VRAM and driver 535 or newer; GVHMR does not run on RTX 50 |
| Disk | 5 GB for the app and basic tools | about 50 GB free for all models (GEM-X ~30 GB, GVHMR ~15 GB) |
| Internet | for the first setup (about 1–2 GB) | tens of GB while installing models |

**No NVIDIA?** Use **GVHMR · Colab** (Google's free GPU in the browser, any OS); Apple Silicon Macs can also run GEM-X locally. MediaPipe is installed as a helper for hands, face and the live camera check; it is no longer a body model.

## Quick install (Windows)

1. Download `MoCapGate-<version>-windows-x64-quickstart.zip`.
2. **Extract the whole archive**: right-click the ZIP → "Extract All…" → a normal folder
   (e.g. Downloads or `C:\MoCapGate`). Do not double-click files inside the ZIP — Windows then
   sees only that one file, and setup stops with a hint. Avoid OneDrive folders and very long paths.
3. (Optional) Run **CHECK-COMPUTER.cmd** — it checks this computer and installs nothing.
4. Run **INSTALL.cmd**. No administrator rights are needed.
   - If a blue **"Windows protected your PC"** window (SmartScreen) appears: MoCapGate builds are not
     signed with a paid certificate, so Windows does not know the publisher. This is not a virus scan.
     Click **"More info" → "Run anyway"** only if you downloaded the archive from the releases page above.
5. INSTALL.cmd does the following (the window stays open until the end and shows a summary):
   - checks that the archive is fully extracted, Windows is 64-bit, at least 5 GB is free and Studio is closed;
   - installs the app for the current user into `%LOCALAPPDATA%\MoCapGate Studio`;
   - downloads FFmpeg, Blender and the MediaPipe helper (hands and face) and adds a demo take;
   - runs the computer check and starts MoCapGate Studio.

   Setup log: `%LOCALAPPDATA%\MoCapGate Studio\logs\install-<date>.log`.
   If setup was interrupted, run INSTALL.cmd again: finished parts are kept and downloads resume.

Without the quickstart: run the `.exe` installer from the release (Start menu → MoCapGate Studio), then follow the steps below.

## First start

1. Open the **Models & tools** tab — the **Installation, step by step** block is at the top.
2. Click **Check the computer**. The check shows the system, memory, disk, graphics card and driver, WSL and
   internet access, and suggests which models fit this PC. Red items block only the related model;
   each one has a fix button or command.
3. Tick the GVHMR and model terms (non-commercial use) and click **Install everything recommended** —
   the app installs what fits the check (basic tools and, on an NVIDIA PC, GEM-X and/or GVHMR). Already
   installed parts are skipped. Single models can be installed with **Install** on their cards.
4. **Open the demo take** — see [Check with the demo take](#check-with-the-demo-take).

### Windows + NVIDIA: WSL2 and Ubuntu

GEM-X and GVHMR run in a WSL2 Linux environment. If it is missing, the app starts the Windows installation:

1. Approve the Windows **administrator** prompt (UAC). This is the only step that needs administrator rights.
2. **Restart** the computer if Windows asks.
3. After the restart an **Ubuntu** window opens. Choose a Linux user name and password (Latin letters;
   this is a separate account inside Ubuntu, not your Windows password). Wait for the `name@computer:~$`
   prompt and close the window.
4. Return to MoCapGate and click **Install everything recommended** again — setup continues.

If Windows reports that virtualization is disabled (`0x80370102`), enable **Intel VT-x / AMD SVM** in
BIOS/UEFI. To check: Task Manager → Performance → CPU → "Virtualization: Enabled".
See [WSL troubleshooting](troubleshooting.en.md#wsl).

### SMPL-X (optional, for GVHMR and an exact body shape)

The SMPL-X model may not be redistributed with the program — every user downloads it personally:

1. Register at [smpl-x.is.tue.mpg.de](https://smpl-x.is.tue.mpg.de/download.php) and accept the
   [SMPL-X licence](https://smpl-x.is.tue.mpg.de/modellicense.html).
2. Download the SMPL-X model archive.
3. In Models & tools → **SMPL-X model** card choose `SMPLX_NEUTRAL.npz` (or the downloaded ZIP).
   The app checks the file and puts it where it is needed.

### Blender (for FBX, Unreal/Unity, your own character)

Installed automatically with the recommended set. An existing Blender is detected; you can set its path in
Settings. BVH and Maya scenes work without Blender.

### Check with the demo take

Open **Demo — Sports2D, two people** in the takes list and press Play: two skeletons should move.
The demo needs no GPU and no SMPL-X. If GEM-X or GVHMR is installed, click **Make the animation** to test
processing on this computer; without NVIDIA or Apple Silicon, test the **GVHMR · Colab** path. The demo tests playback and setup, not mocap accuracy.

## macOS

1. Download `MoCapGate-<version>-macos-arm64-quickstart.zip` (Apple Silicon) or `-x64` (Intel)
   and double-click it to extract.
2. The build is not signed by Apple. The first time you open **INSTALL.command**: right-click
   (Control-click) → Open → Open. If macOS still blocks it: System Settings → Privacy & Security →
   Open Anyway. The scripts do not disable macOS protection.
3. INSTALL.command copies the app into `~/Applications` and installs FFmpeg, Blender, the MediaPipe helper and
   the demo take. No administrator password is needed. Log: `~/Library/Logs/MoCapGate/`.
4. Then continue with [First start](#first-start). On Apple Silicon GEM-X installs locally (about 14 GB;
   if asked, run `xcode-select --install` for Command Line Tools). GVHMR on a Mac runs via GVHMR · Colab.

Each Mac build is tested separately: a successful Windows test does not confirm the Mac build.

## If something goes wrong

- [Troubleshooting](troubleshooting.en.md): SmartScreen, antivirus, proxy, WSL, driver, memory, disk.
- The **Support report** button in Models & tools saves a file with the check results, versions and
  install logs (no videos or animations) to Downloads. You decide whom to send it to.
- Running setup again is safe: finished components and partial downloads are kept.

More: [setup wizard](setup-wizard.en.md), [automatic setup](automatic-setup.en.md), [GVHMR on this PC](gvhmr-managed.en.md),
[GVHMR install recovery](gvhmr-install-recovery.en.md), [models and Maya](models-and-maya.en.md),
[models and licences](models-licences.en.md), [what is verified](verification.en.md).

## For maintainers: building

Builds are made only in the private source project with CPython 3.12.13, `requirements-native.txt`
and `scripts/native_packaging.py`; the unpacked package is tested before the desktop shell is packaged:

```bash
python scripts/native_packaging.py build --out dist/native-package
python tests/test_native_package.py dist/native-package --require-blender
export MOCAPGATE_NATIVE_PACKAGE="$PWD/dist/native-package"
cd apps/studio/desktop && npm ci && npx tauri build
```

Quickstart ZIPs: `scripts/make_windows_quickstart.py --portable <native.zip> --installer <setup.exe>` and
`scripts/make_macos_quickstart.py --portable <portable.zip> --dmg <app.dmg> --arch arm64`.
Details: [native package verification](native-verification.md), [distribution](distribution.md).
