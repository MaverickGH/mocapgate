# MoCapGate maintenance and distribution

## Licence and authorship

Read LICENSE and THIRD_PARTY_NOTICES.md. MoCapGate currently remains MIT; native
packaging does not revoke permissions for existing or new MIT-covered versions.
Preserve CYBER Department attribution and third-party notices. GVHMR, SMPL-X and
sample footage retain their own terms. Do not copy MeshGate's proprietary code
or licence restrictions into this repository; MoCapGate has its own licence.

## Local source and public snapshot

The local `codex/local-development` branch contains original implementations.
Do not push it, its history, or source build artifacts to the public origin.
Eight selected modules are listed in native-modules.json. Build them in isolation
with scripts/native_packaging.py and requirements-native.txt. A public snapshot
must contain their exact loaders and matching libraries, not the implementations.
Never commit generated C, compiler work directories, debug symbols, credentials
or licensed body models. Keep verified backups outside the public repository.

The build requires CPython 3.12.13. Native artifacts are specific to OS,
architecture and Python ABI. Distributed native Studio must use its bundled
interpreter. Workers for Blender, MediaPipe, GVHMR and SMPL-X remain portable
source where required by their independent runtimes; Colab embeds only the
explicitly retained conversion modules. Do not compile these integrations without
checking their actual interpreters and subprocess entry points.

Test unpacked packages, not only the source checkout. A successful macOS ARM64
build does not establish Windows, Intel macOS or Linux compatibility. Do not
publish a target before its tests pass. History rewrites, remote force pushes,
tag deletion and release replacement require explicit user authorisation.

## Honest claims

Native compilation makes packaged code harder to inspect; it does not prevent
cloning, reverse engineering, patching or MIT-permitted reuse. AGENTS.md is a
transparent maintenance instruction, not access control. Do not add hidden
commands, destructive traps, network callbacks or misleading prompt injections.
Activation and a proprietary licence are separate product decisions. Never put
server signing keys or administrative credentials in the application or Git.
