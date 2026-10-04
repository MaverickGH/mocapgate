# Native verification · 2026-10-04

Targets: macOS ARM64, macOS Intel x64, Windows x64 and Linux x64. CPython 3.12.13, Cython 3.3.0, uv 0.12.19.
Independent native CI builds and unpacked-package tests passed on all four targets.

| Check | Result |
|---|---|
| Fresh isolated build of all eight modules | Passed |
| Archive unpacked into a new temporary folder | Passed |
| Studio HTTP API and offline web assets without system Python on PATH | Passed |
| GVHMR JSON → BVH, including multiple people | Passed |
| Demo, take creation and reprocessing | Passed |
| Wrong ABI and missing-input errors | Passed |
| Cancellation of a running job | Passed |
| Actual Blender FBX export | Passed |
| Unit suite against unpacked native libraries | 66 passed, 1 Windows-only skipped |
| Rust cargo check and release desktop app build | Passed |
| Same archive checks on the desktop app resources | Passed |
| Real Sports2D video with MediaPipe heavy | 230 frames, 2 people, 2 BVH; annotated identity check passed |
| Pre-push: safe root accepted; leaked source and unsafe ancestor rejected | Passed |
| Backup: bundle restoration, git fsck, all 26 file hashes | Passed |
| Windows x64 / Intel macOS / Linux x64 native builds | Passed, including bundled runtime, Blender FBX and native unit tests |
| Installed Windows EXE and extracted Linux DEB resources | Passed |
| Final AppImage after ELF relocation and repacking | Passed |
| Public snapshot on all four platforms | Passed |
| Desktop GUI walkthrough, signing and notarization | Not verified |

The Sports2D quality score was 32/100. This verifies execution and identities,
not motion accuracy against reference capture. Licensed body models were not
included; GVHMR GPU inference and SMPL-X surface inference were not tested here.

Reproduce package checks with:

```bash
python3 tests/test_native_package.py dist/native-package --require-blender
```

Real-video checks use `tools/check_multi_person_video.py` and the packaged
`core.pipeline` with MediaPipe heavy in its separate existing environment.
See [Russian guide](code-protection.ru.md) / [English guide](code-protection.en.md).

Build evidence in the release controller:

- [macOS ARM64 job](https://github.com/MaverickGH/app-releases/actions/runs/37201971160) (other target jobs in this run failed; ARM64 succeeded).
- [macOS Intel job](https://github.com/MaverickGH/app-releases/actions/runs/37201696695) (other target jobs failed; Intel succeeded).
- [Windows x64](https://github.com/MaverickGH/app-releases/actions/runs/37202034107).
- [Linux x64](https://github.com/MaverickGH/app-releases/actions/runs/37202975134).

All four final ZIPs also passed static source, SHA-256, CPU architecture and
licence checks. Linux archives are inspected without extraction on macOS,
because runtime terminfo filenames can differ only in letter case.

The [public platform catalog check](https://github.com/MaverickGH/app-releases/actions/runs/37204234987) passed on all four targets. It verifies that a cloned public
snapshot selects the correct native implementation and runs the Studio/package
smoke checks and unit suite with CPython 3.12.13.

[Installed Windows EXE and Linux DEB checks](https://github.com/MaverickGH/app-releases/actions/runs/37204592203) passed, including Blender FBX.
[Final AppImage check](https://github.com/MaverickGH/app-releases/actions/runs/37204559757) passed twice, before and after repacking. linuxdeploy changes ELF RPATH,
so the AppImage manifest records the final library hashes; standalone ZIPs and
the DEB preserve their original library hashes.

The public main/test-pc branches now contain the native distribution history.
Legacy v0.3.0/v0.3.1 tags contain isolated archival descriptions, while previous
release assets retain their IDs and sizes. The full original source history is
backed up locally and archived in the private source repository.
