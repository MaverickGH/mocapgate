# MoCapGate

**Character animation from ordinary video.** Capture a movement, review the skeleton alongside the input and prepare animation for Blender, Maya or a game project.

[Русский](README.md) · **English**

![MoCapGate](docs/assets/mocapgate-banner.png)

## Current versions

- **Windows 10/11 x64: [0.3.3-beta.9](https://github.com/MaverickGH/app-releases/releases/tag/mocapgate-v0.3.3-beta.9)**. [Release in this repository](https://github.com/MaverickGH/mocapgate/releases/tag/v0.3.3-beta.9).
- **macOS Apple Silicon/Intel and Linux x64: [stable 0.3.2](https://github.com/MaverickGH/app-releases/releases/tag/mocapgate-v0.3.2)**. Its interface and features differ. Beta.9 is Windows-only.
- `main` retains the compatible stable 0.3.2 native snapshot. The Windows beta.9 snapshot and documentation are in [`release/0.3.3-beta.9`](https://github.com/MaverickGH/mocapgate/tree/release/0.3.3-beta.9).

## Start beta.9

Download the complete Quickstart ZIP, extract it and run `INSTALL.cmd`. EXE, MSI and a portable native ZIP are also available. Bundled CPython 3.12.13 avoids a system Python requirement. Open Models & tools, check the computer and prepare the recommended components. This is an unsigned beta; verify the release SHA-256 sums.

Body models are experimental GEM-X/SOMA and GVHMR. MediaPipe remains a helper, rather than the ordinary body-model choice. Studio includes motion review, cleanup, foot contacts/IK, versions, queueing and export. BVH/Maya export is direct; FBX/GLB and character retargeting use Blender. Beta.9 adds split-screen cropping and calibrated multi-camera sessions: cropping does not fuse views, while a session requires separate synchronized static-camera videos and measured calibration. Foot drift is withheld without reliable support intervals.

## Verification limits

The release reports **495 passed tests, 17 skipped**, and Blender 4.5.14 FBX export. **GEM-X/GVHMR CUDA inference and WSL were not tested for this build.** Package checks do not verify GPU inference or ground-truth motion accuracy. Review contacts and retargeting on your own character. Colab requires uploading video to Google; local processing keeps video local.

## Code and licences

Public native snapshots contain integration sources plus loaders/native libraries for eight selected implementations. Private development history is not published. Beta.9 code is Apache-2.0; the stable 0.3.2 snapshot in main retains its MIT licence. Models, weights and footage have separate terms, including GVHMR/SMPL-X restrictions.

[Full beta.9 guide](https://github.com/MaverickGH/mocapgate/blob/release/0.3.3-beta.9/README.en.md) · [Stable 0.3.2 guide](README.stable.en.md) · [Issues](https://github.com/MaverickGH/mocapgate/issues)
