#!/bin/bash
# Per-user setup from a downloaded package; no GitHub login or administrator needed.
set -euo pipefail
project_root="$(cd "$(dirname "$0")/.." && pwd)"
skip_launch=0; skip_ai=0; model=""; plan=0; surface_runtime=0
while [ "$#" -gt 0 ]; do
  case "$1" in
    --skip-launch) skip_launch=1 ;;
    --skip-ai) skip_ai=1 ;;
    --smplx-model) shift; model="$1" ;;
    --surface-runtime) surface_runtime=1 ;;
    --plan) plan=1 ;;
    *) echo "Unknown argument: $1" >&2; exit 2 ;;
  esac
  shift
done
if [ "$plan" = 1 ]; then echo 'Install uv, isolated Python 3.12/numpy and MediaPipe; install supplied DMG in ~/Applications; open Studio.'; exit 0; fi
if [ "$(uname -s)" != Darwin ]; then echo 'This setup is for macOS.' >&2; exit 2; fi
export PATH="$HOME/.local/bin:$PATH"
if ! command -v uv >/dev/null; then
  uv_script="$(mktemp)"
  curl --fail --location https://astral.sh/uv/install.sh --output "$uv_script"
  sh "$uv_script"
fi
runtime="$HOME/.cache/mocapgate/studio-runtime"
if [ ! -x "$runtime/bin/python" ]; then uv python install 3.12; uv venv --python 3.12 "$runtime"; fi
py="$runtime/bin/python"
uv pip install --python "$py" numpy==1.26.4 imageio-ffmpeg==0.6.0
export PYTHONUTF8=1 PYTHONDONTWRITEBYTECODE=1 MOCAPGATE_PYTHON="$py"
app="$HOME/Applications/MoCapGate Studio.app"
dmg="$(find "$project_root" -maxdepth 1 -name '*.dmg' -print -quit)"
if [ -n "$dmg" ]; then
  mount_point="$(mktemp -d -t mocapgate-volume)"
  # Our DMG displays the bundled MIT license before mounting. Supply its answer
  # for unattended per-user setup; hdiutil still verifies the disk image normally.
  printf 'Y\n' | hdiutil attach -nobrowse -mountpoint "$mount_point" "$dmg"
  trap 'hdiutil detach "$mount_point" >/dev/null || true' EXIT
  source_app="$(find "$mount_point" -maxdepth 2 -name 'MoCapGate Studio.app' -print -quit)"
  test -n "$source_app"
  mkdir -p "$HOME/Applications"
  ditto "$source_app" "$app"
  hdiutil detach "$mount_point"; trap - EXIT
fi
app_root="$project_root"
if [ -f "$app/Contents/Resources/mocapgate/mocapgate.py" ]; then app_root="$app/Contents/Resources/mocapgate"; fi
test -f "$app_root/mocapgate.py"
"$py" "$project_root/scripts/install_ffmpeg.py"
"$py" "$project_root/scripts/install_example.py" "$app_root"
if [ "$skip_ai" = 0 ]; then
  "$py" "$app_root/mocapgate.py" setup mediapipe --model heavy
  "$py" "$project_root/scripts/prepare_models.py" "$app_root"
fi
if [ -n "$model" ] || [ "$surface_runtime" = 1 ]; then
  if [ -n "$model" ]; then
    test -f "$model"
    model="$(cd "$(dirname "$model")" && pwd)/$(basename "$model")"
  fi
  surface="$HOME/.cache/mocapgate/smplx-runtime"
  if [ ! -x "$surface/bin/python" ]; then uv venv --python 3.12 "$surface"; fi
  torch_version=2.3.0
  # PyTorch stopped publishing Intel macOS wheels after 2.2.x.
  if [ "$(uname -m)" = x86_64 ]; then torch_version=2.2.2; fi
  uv pip install --python "$surface/bin/python" "torch==$torch_version" smplx==0.1.28 numpy==1.26.4
  "$surface/bin/python" -c 'import torch, smplx, numpy; x=torch.ones(3,requires_grad=True); x.square().sum().backward(); assert numpy.isfinite(x.grad.numpy()).all(); print("SMPL-X runtime ready:",torch.__version__)'
  if [ -n "$model" ]; then
    export MOCAPGATE_SETUP_MODEL="$model" MOCAPGATE_SETUP_SURFACE_PYTHON="$surface/bin/python"
    "$py" "$project_root/scripts/configure_surface.py" "$app_root"
  fi
fi
"$py" "$app_root/mocapgate.py" doctor
if [ "$skip_launch" = 0 ]; then
  if [ -d "$app" ]; then open "$app"; else "$py" "$app_root/mocapgate.py" studio; fi
fi
