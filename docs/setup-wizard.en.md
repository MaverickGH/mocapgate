# Setup wizard

[Русский](setup-wizard.ru.md) · [Installation](install.en.md) · [Troubleshooting](troubleshooting.en.md)

Since 0.3.3 beta (Windows prerelease); stable 0.3.2 has no wizard.
**Models & tools** tab → **Installation, step by step** block.

## 1. Check the computer

Installs nothing. Checks run in parallel (up to ~20 s):

- system: 64-bit OS, Windows build or macOS version, Apple Silicon / Intel;
- memory (at least 8 GB for GEM-X and GVHMR, 16+ recommended);
- disk space for takes and models (base 5 GB; GEM-X ~14 GB on a Mac, ~30 GB on Windows/WSL; GVHMR ~15 GB);
- takes folder: writable, not cloud-synced, path length, Windows long paths;
- non-ASCII characters in the user profile path, proxy;
- NVIDIA GPU, driver, VRAM (GEM-X 8 GB, GVHMR 6 GB), GVHMR architecture support;
- WSL (Windows): installed, responding, version 2, assigned memory;
- Command Line Tools (Mac), detected tools;
- access to download servers, HTTPS interception, rate limits.

Every problem comes with an explanation and a **fix button or command**. A red item blocks only the
related model. At the bottom is a recommendation: Apple Silicon → GEM-X locally and GVHMR in Colab;
NVIDIA → GEM-X and/or GVHMR locally; no NVIDIA → GVHMR · Colab.

**WSL memory.** If WSL has too little memory, the fix button offers to write `memory` and `swap` to
`%UserProfile%\.wslconfig`. It writes only after your confirmation; the previous file is kept as
`.wslconfig.mocapgate-backup`, other lines are preserved, then WSL restarts (`wsl --shutdown`). The button
refuses while processing or installation is running.

## 2. Install everything recommended

Installs **only missing parts** in order: FFmpeg and Blender → WSL2 and Ubuntu (Windows, if needed) →
GEM-X → GVHMR (as recommended by the check). For GVHMR, accept the GVHMR and model terms (non-commercial
use). If the internet drops, press the button again: downloads resume and partial files never count as
installed. After installing WSL, Windows may ask for a restart: restart and press Install everything
recommended again — installation continues.

The SMPL-X model (for GVHMR) is uploaded separately in the SMPL-X body model card: `SMPLX_NEUTRAL.npz`
or the archive from the site.

## 3. Try it

**Open the demo take** opens the Sports2D example. The demo tests playback, not accuracy.

## Check system readiness

The separate Check system readiness button inspects what is installed: detected tools and environments,
and for GVHMR/GEM-X the PyTorch import and CUDA availability. Check the computer is for before
installation; Check system readiness is for after.

## Without the app window

```bash
python3 mocapgate.py preflight            # same as Check the computer
python3 mocapgate.py preflight --json --no-network --lang en
python3 mocapgate.py setup recommended    # FFmpeg, ffprobe, Blender
```

`preflight` exit code: 0 — no blocking problems, 2 — blockers found.

Quickstart archives contain **CHECK-COMPUTER.cmd** (Windows) / **CHECK-COMPUTER.command** (Mac) — the same
check, installing nothing — and **INSTALL.cmd** / **INSTALL.command**, which install the app, FFmpeg,
Blender, the MediaPipe helper and the demo take.

## Support report

**Support report** saves `MoCapGate-support-<date>.zip` to Downloads. It contains the version and platform,
the computer check result, component status, settings (without fields containing tokens or keys; paths may
include your user name), a short list of the last 50 takes (ID, model, status, error, frames, FPS) and
installation logs. **No videos, animations or models.** The app never sends it anywhere — you decide whom
to give it to.

## Logs

- in-app installation: the `logs` folder next to the settings (macOS — `~/Library/Application Support/MoCapGate/logs`,
  Windows — `%APPDATA%\MoCapGate\logs`, Linux — `~/.config/mocapgate/logs`); the last 20 are kept;
- quickstart: Windows — `%LOCALAPPDATA%\MoCapGate Studio\logs\install-<date>.log`, Mac — `~/Library/Logs/MoCapGate/`;
- desktop window: macOS — `~/Library/Logs/dev.mocapgate.studio/studio.log`, Windows — `%LOCALAPPDATA%\dev.mocapgate.studio\logs\studio.log`.

## Update check

At most once every 6 hours Studio requests the release list from `api.github.com/repos/MaverickGH/app-releases`
and shows "New version … — download". No data about you or your takes is sent, but GitHub sees your IP
address. There is no auto-update. To disable: Settings → Check for new versions (anonymous request to GitHub).
