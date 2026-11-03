# Automatic MoCapGate setup

Native Studio includes Python and uv; no separate Python installation is needed.

1. Open **Models & tools → Installation, step by step → Check the computer**. The check reports the system, memory, disk, GPU, WSL and access to download servers, and recommends models. [About the wizard](setup-wizard.en.md).
2. Click **Install everything recommended**. Only missing parts are installed: FFmpeg and Blender, plus — depending on the check — WSL2/Ubuntu (Windows), GEM-X and/or GVHMR. For GVHMR, accept the model terms. If the internet drops, press the button again; downloads resume.
3. Open **Takes → + Import video**, select **GEM-X · SOMA**, **GVHMR · Colab** or **GVHMR · this PC**, and click **Make the animation**. BVH and Maya scenes work without Blender; FBX and engine export use the detected or managed Blender.

Tools are stored per user under `~/.cache/mocapgate/` (GEM-X and GVHMR on Windows live inside WSL). FFmpeg is in `tools`, Blender in `tools/blender`, and the MediaPipe helper (hands and face) in `mediapipe`. Studio detects managed FFmpeg after restarting without changing the system PATH and saves Blender's executable path automatically.

## GVHMR with NVIDIA

In Models & tools, open the GVHMR card (or use Install everything recommended), read and accept the model terms, then click **Install**. Windows uses WSL2 / Ubuntu. When Ubuntu is missing, Studio launches Windows' WSL installer. Accept the administrator prompt, restart if Windows requests it, open Ubuntu once to finish its initial setup, then repeat the GVHMR installation in Studio. No terminal commands or manual Python/repository paths are needed. Ubuntu dependencies, Python, packages and the four required checkpoints are configured automatically.

Linux GVHMR requires an NVIDIA CUDA driver. Missing system dependencies are installed through apt-get and pkexec with an OS authorization prompt. Other distributions without these tools need their own package manager. The basic FFmpeg / Blender installer supports Windows x64, macOS ARM64/Intel and Linux x64. Macs use GVHMR · Colab (local GVHMR requires CUDA); Apple Silicon Macs can also install GEM-X locally (about 14 GB).

## SMPL-X: one manual download

Register at [SMPL-X](https://smpl-x.is.tue.mpg.de), accept the authors' terms, and download the model. In the **SMPL-X body model** card click **Upload SMPLX_NEUTRAL.npz or the .zip from the site** and choose `SMPLX_NEUTRAL.npz` or the downloaded `models_smplx_v1_1.zip`. Do not upload an SMPL or SMPL-H model.

Studio validates the file, places it under its user settings in `body_models/SMPLX_NEUTRAL.npz`, records the path, and copies it into GVHMR's expected directory. When a GVHMR runtime is not configured, Studio installs separate CPU SMPL-X tools for exact bones and body surfaces, requiring an additional download. Licensed model files are never bundled.

After the GVHMR environment and model are ready, select **GVHMR · this PC** for your video. GPUs with up to 10 GB use four-frame preprocessing batches; this does not guarantee that arbitrarily long videos fit in memory. GPU inference must be verified on a computer with a supported NVIDIA GPU.

## Interrupted setup

The installation log remains visible. Repeat the setup to reuse working components. Partial downloads never count as installed tools. Cancel stops the installation and allows a later retry. Network access, GPU drivers and any WSL restart requested by Windows remain prerequisites.

Windows: an installed distribution is selected automatically. Under Preferences and advanced paths → Advanced GVHMR paths → Runtime → WSL, enter the exact name of any installed distribution, or leave it blank for automatic selection. Automatic system package installation requires apt-get (for example Ubuntu or Debian); other distributions require manual dependency preparation. The log preserves the original WSL error.
