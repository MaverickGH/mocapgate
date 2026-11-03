# Models and Maya export

These features exist since 0.3.3 beta (Windows prerelease); stable 0.3.2 lacks them. Maya rigs in detail: [maya-rigs.en.md](maya-rigs.en.md).

1. Open **Models & tools → Installation, step by step → Check the computer → Install everything recommended**. Studio installs missing FFmpeg, ffprobe, Blender and suitable models ([setup wizard](setup-wizard.en.md)).
2. Select GVHMR in Colab, local GVHMR on NVIDIA, or experimental GEM-X. MediaPipe is removed from body model choices. Existing takes remain readable; MediaPipe is installed as a helper for GVHMR hands/face and GEM-X facial expressions.
3. Local GVHMR requires a working WSL2 distribution on Windows. Complete Ubuntu's first launch, then run installation. Upload your own `SMPLX_NEUTRAL.npz` under its provider's terms; Studio places it and configures paths.
4. GEM-X installs in an isolated environment with pinned GEM-X/SOMA revisions and downloaded models. Allow about 14 GB of free disk space on Apple Silicon and about 30 GB on Windows/WSL. Mac needs Git / Command Line Tools; Windows uses WSL2/NVIDIA. Apple Silicon uses ONNX/CoreML and CPU geometry. Platform validation is separate. Start with one person and a stationary camera: SOMA has 77 joints and is not interpreted as SMPL-X.
5. **Takes → + Import video**: click the upload area or drop footage, select a model and export FPS, then process it.

ffprobe reads source FPS and timestamps. GVHMR/GEM-X inputs are truly resampled to 30 FPS with FFmpeg, preserving playback speed and duration. Export at source rate, 30, 60 or 120 FPS uses time-based rotation interpolation; a higher export rate does not add captured observations.

In **Settings → Maya character**, select Man_Rig, Capture skeleton or Custom Maya rig (a local `.ma` with compatible MoCapGate/Mixamo joint names or a rig profile). **Download Maya scene (.ma)** contains Man_Rig (geometry, skinning, animation) when Man_Rig is selected; otherwise the capture skeleton (with a `FaceExpressions` node when expressions are enabled). Use **Open character in Maya** when Maya is detected. Direct `.ma` files have integer keys 1…N and the export time unit. The Maya worker transfers bind-relative world rotations, bakes every frame and saves a separate `character-animation.ma`. Textures were not supplied; the rig includes geometry, joints and skinning. Personal texture paths and saved Maya UI scripts are removed from the bundled copy. Facial coefficients are not automatically mapped to this rig's facial controls. The supplied rig is distributed with the user's permission; its author/source have not yet been identified.

Hand stabilization limits rotation outliers and smooths discontinuities. SMPL-X stabilization occurs before skinning so the surface and skeleton agree. It cannot recover fingers hidden in the footage. Increased BVH frame-time precision and native Maya export prevent rounding such as `94.999…`. `core.maya_export.repair_key_times` can repair near-integer drift in a copy of an old scene while preserving intentional subframe keys and channel values; it does not repair poses.

Maya is unavailable on the local validation computer. Integer keys, units and rotation calculations are tested; actual Maya rig transfer and scene saving still require a Maya test. Installation logs are readable in Models & tools. WSL component rollback must be resolved before a model installer can run; user distributions are preserved.

Sources: [GEM-X](https://github.com/NVlabs/GEM-X), [SOMA-X](https://github.com/NVlabs/SOMA-X), [Maya currentUnit](https://help.autodesk.com/cloudhelp/2024/ENU/Maya-Tech-Docs/CommandsPython/currentUnit.html).

## End-to-end checks (7 October 2026)

Animation jobs display the current stage and elapsed time. Stages without a
frame counter use an indeterminate indicator rather than an invented percentage.
Export and reprocessing are unavailable while a take is busy. Native `.ma`
downloads use the same Downloads-folder saving flow as BVH/FBX. The export
summary shows the current frame rate and Maya rig. Reprocess after changing FPS;
the recognition result remains cached.

With Man_Rig selected, the downloaded `.ma` contains Man_Rig (geometry, skinning,
animation); otherwise the capture skeleton. FBX always contains the capture
skeleton. Opening the character in Maya transfers the animation to the selected rig. SOMA's extra metacarpal joint
is accounted for when matching finger phalanges to Mixamo. Mapping is tested;
the retarget operation inside Maya remains unverified on this machine.

SAM-Body4D remains a separate experiment. Real 25 FPS video preparation, the
no-CUDA diagnostic, raw-parameter capture and comparison-report checks passed.
CUDA inference and MHR-to-rig animation conversion remain unverified; SAM-Body4D
is not advertised as a working Studio backend. Physical camera capture, Maya
and Windows/CUDA need separate manual checks.
