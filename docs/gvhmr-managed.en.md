# GVHMR from the app · 0.3.3 beta

[Русский](gvhmr-managed.ru.md)

On Windows with an NVIDIA GPU, open **Models & tools**. The simplest path is **Check the computer →
Install everything recommended**: the wizard installs WSL, GVHMR and (when suitable) GEM-X. Step by step:

1. Install the current NVIDIA Windows driver. A separate CUDA Toolkit installation
   is not needed. If WSL is missing, the wizard (or the fix button in the computer check)
   starts the WSL / Ubuntu installation; approve the Windows administrator prompt, wait for
   installation and restart. If requested, open Ubuntu once to create its user.
2. Read the GVHMR/model terms, accept them and click **Install** in the GVHMR card
   (or Install everything recommended again). The app installs Ubuntu dependencies,
   Python 3.10, a pinned GVHMR revision and the four inference checkpoints. Installation
   progress appears in the job log.
3. Obtain **SMPLX_NEUTRAL.npz** from the SMPL-X authors and upload it (or the ZIP from
   the site) in the **SMPL-X body model** card. The app validates the model, remembers its
   location and copies it into GVHMR's model directory. You do not need to type paths.
4. Wait for **Ready**, import a video and select **GVHMR · this PC**.
   The app converts the video to 30 FPS, runs GVHMR in WSL and imports the motion.
   Export BVH or use Blender to export FBX.

For an NVIDIA GPU, start with a 5–10 second video of one person and a
stationary camera; enable the stationary-camera option in the take. GPUs with
up to 10 GB automatically process cropped frames in batches of four to reduce
VRAM usage. This does not guarantee that every long clip will fit in memory.
Actual GPU inference requires verification on supported hardware.

Linux uses a separate local environment; install git, ffmpeg, a C/C++ compiler
and Python 3.10 with venv and Tk (Ubuntu: python3-venv / python3-tk)
through your package manager first. Local CUDA GVHMR is unavailable on macOS;
use GVHMR · Colab there; Apple Silicon Macs can also run GEM-X locally.

Manual GVHMR/Python configuration remains available under advanced settings.
Uploaded SMPL-X now takes priority and is synchronized to the connected runtime.
Mesh and precise rest-bone calculations run in the model environment, so NumPy
does not need to be installed inside the native Studio package.

GVHMR and SMPL-X retain their own non-commercial terms. The app does not include
licensed body models. This is a beta (0.3.3, Windows prerelease; stable 0.3.2 lacks this path).
GVHMR inference on Windows/WSL is confirmed by a user report on beta.4/5; NVIDIA inference was
not run on our test machine. [What is verified](verification.en.md).

Driver and WSL setup: [NVIDIA guide](https://docs.nvidia.com/cuda/wsl-user-guide/index.html).
Body model: [SMPL-X authors](https://smpl-x.is.tue.mpg.de).
