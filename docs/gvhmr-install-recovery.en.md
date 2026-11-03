# Recovering GVHMR installation

`WSL_E_WSL_OPTIONAL_COMPONENT_REQUIRED` / `0x80040321` means the Windows WSL component is unavailable. Check Windows Subsystem for Linux and Virtual Machine Platform. If Windows rolls back enabling them after restart, the installer displays available feature state, recent Setup/Application events and relevant CBS.log entries. Reading feature state may require an administrator PowerShell. The application does not remove network adapters or change Windows services.

Errors involving `0x800706be`, `0x800f0922`, `NetSetupAI.dll`, `NetSetupEngine.dll` or `vms_pp` require Windows servicing/network diagnostics. Duplicate TAP adapters may warrant investigation; a causal connection is unproven. Do not remove adapters without understanding their purpose and obtaining the owner's consent.

Distributions in `Installing` state are skipped during automatic selection. Finish their initial setup or select another ready distribution in WSL settings. Existing distributions and data are preserved; the app does not run `wsl --unregister`.

System dependencies include `python3-dev`, compiler tools, venv and Tk. If Google Drive limits downloads, the installer uses the pinned `camenduru/GVHMR` mirror. Each of the four files must match its expected size and SHA-256 before replacing an existing file. Licensed SMPL-X files are still obtained separately from their authors.

A user reported successful WSL2 CUDA operations and GVHMR processing of 60 test-video frames with two people, finite JSON trajectories and a static camera. This is an external-device report; processing a user video through Studio was not verified in that report.
