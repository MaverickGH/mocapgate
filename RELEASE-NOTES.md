# MoCapGate Studio 0.3.3-beta.9 — Windows x64

Beta test build for Windows x64.

## Downloads

- `MoCapGate-0.3.3-beta.9-windows-x64-quickstart.zip` — recommended: portable native runtime, setup/check scripts and NSIS installer in one archive. Extract the complete archive, then run `INSTALL.cmd`.
- `MoCapGate-0.3.3-beta.9-windows-x64-setup.exe` — per-user NSIS installer.
- `MoCapGate-0.3.3-beta.9-windows-x64.msi` — Windows Installer package.
- `MoCapGate-0.3.3-beta.9-windows-x64-native.zip` — portable native runtime package for manual use.
- `SHA256SUMS.txt` — SHA-256 digests for the downloadable packages.

## Verified on this build

- Windows x64 native package integrity and unpacked-package startup without system Python.
- Processing, error handling, cancellation, and packaged runtime suite: 495 tests passed; 17 skipped.
- Blender FBX export using Blender 4.5.14.
- The installer and quickstart package were generated from the same beta.9 native package.
- Changes in this beta include split-screen multi-view cropping/session support and evidence-aware motion-quality reporting. A drift value is withheld when reliable foot-support intervals cannot be detected.

## Not verified here

GEM-X/GVHMR CUDA inference and WSL integration were not run on this PC: WSL enumeration returned access denied, and this PC reports a GeForce GTX 1080 rather than the RTX 8 GB+ hardware described for that workflow. Do not treat the GPU models as tested by this release.

This is an unsigned beta. SmartScreen may warn on first launch. Installers and dependencies may require internet access. The project source is not included in this release upload.
