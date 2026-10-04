# Native MoCapGate packaging

Release **0.3.2** provides independent **macOS ARM64, macOS Intel x64,
Windows x64 and Linux x64** packages with bundled **CPython 3.12.13**.
Eight implementations are replaced by Cython loaders in the packages and
public snapshot. Originals and previous history remain in a private source
repository and verified backups.

MoCapGate remains **MIT**. Compilation makes implementations harder to inspect;
it does not prevent cloning, reverse engineering or licence-permitted reuse.
Activation and proprietary licensing are separate decisions.
[Detailed Russian guide](code-protection.ru.md).

`native-modules.json` selects CLI, Studio server, pipeline, retargeting, cleanup,
quality reports, component management and motion details. The native libraries
stay beside their loaders so existing `__file__` paths remain valid. Loaders
check OS, architecture and CPython ABI. Package validation verifies library
SHA-256 hashes and rejects protected originals, compiler C/C++, debug files,
source maps and Python caches.

MediaPipe/detail/mesh workers, the GVHMR runner, Blender integration and their
supporting modules remain source for compatibility with their separate Python
runtimes. GVHMR/BVH/SMPL conversion, rotations and skeleton helpers remain source
for the self-contained Colab notebook. Browser JavaScript remains readable.
Python, uv and third-party licence texts are included.

## Build and test

Use CPython 3.12.13 and a C/C++ compiler (MSVC on Windows). Build dependencies
are pinned in `requirements-native.txt`. Build each OS/architecture separately.

```bash
uv python install 3.12.13
uv venv --python 3.12.13 .venv-native
uv pip install --python .venv-native/bin/python -r requirements-native.txt
.venv-native/bin/python scripts/native_packaging.py build --out dist/native-package
.venv-native/bin/python tests/test_native_package.py dist/native-package --require-blender
.venv-native/bin/python scripts/native_packaging.py zip dist/native-package --out dist/MoCapGate-native.zip
```

On Windows use `.venv-native\Scripts\python.exe`. Choose a new output directory;
builds refuse to overwrite packages or compile public loaders as originals.

Start with `START.sh` or `START_WINDOWS.cmd`; CLI commands use
`python/bin/python3.12 mocapgate.py …` or `python\python.exe mocapgate.py …`.
No system Python is required. AI environments, models and Blender are separate.
For desktop builds set `MOCAPGATE_NATIVE_PACKAGE` to the absolute verified package
path, then run `npm ci` and `npx tauri build` in `apps/studio/desktop`.
Tauri packages only that native folder and uses its bundled interpreter.

The package test creates and unpacks a ZIP, launches Studio without system
Python on PATH, checks HTTP/local web assets, single/multiple-person BVH,
demo output, take creation/reprocessing, missing-input errors and job cancellation.
It exports an actual FBX when Blender is available (`--require-blender` disallows
skipping), then runs the unit suite against the unpacked native libraries.
All four targets were built and tested on their own CI runners, including
actual Blender FBX exports and native unit tests. macOS ARM64 was also tested
locally. A real Sports2D clip produced two stable IDs and two BVH files over
230 frames, with a quality score of 32/100: functional verification, not a
precision reference. Installers are unsigned and macOS notarization was not
performed. See the [verification record](native-verification.md).

Builds use private source through a read-only deploy key; only checked binary
artifacts are uploaded. The release controller workflows are maintained in
[MaverickGH/app-releases](https://github.com/MaverickGH/app-releases/tree/main/.github/workflows).

## Source and publication

Originals stay in `codex/local-development`. Verified history, working files and
latest release assets were backed up outside the public repository. The local
origin push URL is disabled, while fetch still works. The pre-push hook blocks
the development branch and checks every reachable commit of a candidate public
snapshot. Hooks are local safeguards and do not follow ordinary clones.

```bash
python3 scripts/native_packaging.py snapshot dist/native-package --out /path/outside/repo/public-preview
```

The public snapshot contains `native-manifests` for all four platforms and
matching libraries beside the loaders. A clone requires CPython 3.12.13;
portable ZIPs and installers already contain their interpreter.

The owner authorized the public history rewrite. A new root commit replaces
public branches using `--force-with-lease`; older tags carry archival descriptions
while old release assets remain available. Old Git objects and external copies
may remain accessible, and MIT permissions are preserved.
