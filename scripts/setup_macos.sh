#!/bin/bash
# Per-user setup from a downloaded package; no GitHub login or administrator needed.
# Exit codes: 0 done, 1 a setup step failed, 2 bad argument / not macOS, 3 Studio is running,
# 4 package incomplete, 5 not enough disk space. --check-only runs the checks and
# `mocapgate.py preflight` without installing. Log: ~/Library/Logs/MoCapGate/install-<timestamp>.log
set -euo pipefail
project_root="$(cd "$(dirname "$0")/.." && pwd)"
skip_launch=0; skip_ai=0; model=""; plan=0; surface_runtime=0; check_only=0
while [ "$#" -gt 0 ]; do
  case "$1" in
    --skip-launch) skip_launch=1 ;;
    --skip-ai) skip_ai=1 ;;
    --smplx-model) shift; model="$1" ;;
    --surface-runtime) surface_runtime=1 ;;
    --check-only) check_only=1 ;;
    --plan) plan=1 ;;
    *) echo "Unknown argument: $1" >&2; exit 2 ;;
  esac
  shift
done
if [ "$plan" = 1 ]; then echo 'Install supplied DMG in ~/Applications; use bundled Python/uv for native packages; prepare FFmpeg, FFprobe, Blender and optional MediaPipe. Legacy source packages use an isolated Python runtime.'; exit 0; fi
if [ "$(uname -s)" != Darwin ]; then echo 'This setup is for macOS.' >&2; exit 2; fi

log_dir="$HOME/Library/Logs/MoCapGate"
log=""
if mkdir -p "$log_dir" 2>/dev/null; then
  log="$log_dir/$([ "$check_only" = 1 ] && echo check || echo install)-$(date +%Y%m%d-%H%M%S).log"
  exec > >(tee -a "$log") 2>&1
fi
step='Подготовка / Preparing'
step() { step="$1"; printf '\n==> %s\n' "$1"; }
stop() { # code, ru, en
  printf '\n[X] %s\n    %s\n' "$2" "$3"
  [ -n "$log" ] && echo "Журнал / Log: $log"
  echo "Решение частых проблем / Troubleshooting: $project_root/docs/troubleshooting.ru.md · troubleshooting.en.md"
  exit "$1"
}
on_error() {
  local code="$1"
  printf '\n[X] Ошибка на шаге: %s\n    Setup failed at step: %s (exit %s)\n' "$step" "$step" "$code"
  echo 'Запустите INSTALL.command ещё раз: готовые компоненты сохраняются, загрузки продолжаются.'
  echo 'Run INSTALL.command again: finished components are kept and downloads resume.'
  [ -n "$log" ] && echo "Журнал / Log: $log"
  echo "Решение частых проблем / Troubleshooting: $project_root/docs/troubleshooting.ru.md · troubleshooting.en.md"
}
trap 'on_error $?' ERR

step 'Проверка системы и пакета / Checking system and package'
echo "macOS $(sw_vers -productVersion 2>/dev/null || echo '?'), $(uname -m)"
missing=""
for required in mocapgate.py core scripts/install_example.py scripts/prepare_models.py; do
  [ -e "$project_root/$required" ] || missing="$missing $required"
done
if [ -f "$project_root/native-manifest.json" ]; then
  for required in python/bin/python3.12 uv; do [ -e "$project_root/$required" ] || missing="$missing $required"; done
fi
if [ -n "$missing" ]; then
  stop 4 "Пакет распакован не полностью, нет:$missing. Распакуйте архив заново целиком." "The package is incomplete, missing:$missing. Extract the whole archive again."
fi
free_gb=$(( $(df -Pk "$HOME" | awk 'NR==2 {print $4}') / 1024 / 1024 ))
echo "Свободно / Free space: $free_gb GB"
if [ "$free_gb" -lt 5 ]; then
  if [ "$check_only" = 0 ]; then stop 5 "Свободно $free_gb ГБ, нужно не меньше 5 ГБ. Освободите место и запустите снова." "Only $free_gb GB free, at least 5 GB is required. Free up space and run again."; fi
  echo "[!] Свободно меньше 5 ГБ — установка не начнётся. / Less than 5 GB free — setup will not start."
fi
if pgrep -f 'MoCapGate Studio.app/Contents/MacOS' >/dev/null 2>&1 || pgrep -f 'mocapgate.py studio' >/dev/null 2>&1; then
  if [ "$check_only" = 0 ]; then stop 3 'MoCapGate Studio запущен. Закройте приложение и запустите установку снова.' 'MoCapGate Studio is running. Quit the app and run setup again.'; fi
  echo '[!] MoCapGate Studio запущен — перед установкой закройте его. / MoCapGate Studio is running — quit it before installing.'
fi

# Runs `mocapgate.py preflight --json` when this version has it; prints a summary. Never fails setup.
run_preflight() { # python, app_root, network(1/0)
  local python="$1" root="$2" output code=0
  if ! ls "$root"/core/preflight* >/dev/null 2>&1; then
    echo 'Проверка компьютера недоступна в этой версии. / Computer check is not available in this version.'; return 0
  fi
  local args=("$root/mocapgate.py" preflight --json)
  [ "$3" = 1 ] || args+=(--no-network)
  output="$("$python" "${args[@]}" 2>&1)" || code=$?
  if printf '%s' "$output" | grep -qE 'invalid choice|unrecognized arguments'; then
    echo 'Проверка компьютера недоступна в этой версии. / Computer check is not available in this version.'; return 0
  fi
  printf '%s' "$output" | "$python" -c '
import json, os, sys
text = sys.stdin.read()
try:
    report = json.loads(text[text.index("{"):])
    checks = report["checks"]
except (ValueError, KeyError, TypeError):
    print(text); sys.exit(0)
lang = "ru" if os.environ.get("LANG", "").startswith("ru") else "en"
pick = lambda v: v if isinstance(v, str) else (v or {}).get(lang) or (v or {}).get("en") or ""
marks = {"ok": "[OK]", "warn": "[!] ", "fail": "[X] "}
for c in checks:
    print(marks.get(c.get("level"), "[i] "), pick(c.get("title")))
    if c.get("level") in ("warn", "fail"):
        if pick(c.get("detail")): print("      " + pick(c.get("detail")))
        fix = c.get("fix") or {}
        value = "MoCapGate Studio → «Модели и инструменты» / Models & tools" if fix.get("kind") == "action" else str(fix.get("value") or "")
        line = ": ".join(x for x in (pick(fix.get("label")), value) if x)
        if line: print("      -> " + line)
rec = report.get("recommend") or {}
if rec.get("models") or rec.get("reason"):
    print("Рекомендуемые модели / Recommended models:", ", ".join(rec.get("models") or []), "—", pick(rec.get("reason")))
' || true
  return "$code"
}

app="$HOME/Applications/MoCapGate Studio.app"
if [ "$check_only" = 1 ]; then
  step 'Проверка компьютера / Computer check'
  check_root=""
  for candidate in "$project_root" "$app/Contents/Resources/mocapgate"; do
    if [ -f "$candidate/mocapgate.py" ] && [ -x "$candidate/python/bin/python3.12" ]; then check_root="$candidate"; break; fi
  done
  if [ -z "$check_root" ]; then
    echo '[!] Не найден встроенный Python — сначала запустите INSTALL.command. / Bundled Python not found — run INSTALL.command first.'
    exit 0
  fi
  result=0; run_preflight "$check_root/python/bin/python3.12" "$check_root" 1 || result=$?
  [ "$result" = 2 ] && exit 2
  exit 0
fi

export PATH="$HOME/.local/bin:$PATH"
dmg="$(find "$project_root" -maxdepth 1 -name '*.dmg' -print -quit)"
if [ -n "$dmg" ]; then
  step 'Установка приложения в ~/Applications / Installing the app into ~/Applications'
  mount_point="$(mktemp -d -t mocapgate-volume)"
  # Our DMG displays the bundled project license before mounting. Supply its answer
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
step 'Подготовка Python / Preparing Python'
native_package=0
if [ -f "$app_root/native-manifest.json" ]; then
  native_package=1
  py="$app_root/python/bin/python3.12"
  test -x "$py" && test -x "$app_root/uv" || { echo 'Incomplete native package: extract the complete ZIP or reinstall the DMG.' >&2; exit 1; }
  "$py" -c 'import sys; assert sys.version_info[:3] == (3,12,13), "Native Studio requires bundled CPython 3.12.13"'
  export PATH="$app_root:$PATH"
else
  if ! command -v uv >/dev/null; then
    uv_script="$(mktemp)"
    curl --fail --location https://astral.sh/uv/install.sh --output "$uv_script"
    sh "$uv_script"
  fi
  runtime="$HOME/.cache/mocapgate/studio-runtime"
  if [ ! -x "$runtime/bin/python" ]; then uv python install 3.12; uv venv --python 3.12 "$runtime"; fi
  py="$runtime/bin/python"
  uv pip install --python "$py" numpy==1.26.4 imageio-ffmpeg==0.6.0
fi
export PYTHONUTF8=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 MOCAPGATE_PYTHON="$py"
step 'FFmpeg, Blender и базовые инструменты / FFmpeg, Blender and basic tools'
if [ "$native_package" = 1 ]; then "$py" "$app_root/mocapgate.py" setup recommended
else "$py" "$project_root/scripts/install_ffmpeg.py"; fi
step 'Демо-дубль Sports2D / Sports2D demo take'
"$py" "$project_root/scripts/install_example.py" "$app_root"
if [ "$skip_ai" = 0 ]; then
  step 'MediaPipe и модели людей, кистей и лица / MediaPipe and person, hand and face models'
  "$py" "$app_root/mocapgate.py" setup mediapipe --model heavy
  "$py" "$project_root/scripts/prepare_models.py" "$app_root"
fi
if [ -n "$model" ] || [ "$surface_runtime" = 1 ]; then
  step 'Инструменты SMPL-X / SMPL-X tools'
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
step 'Итоговая проверка / Final check'
"$py" "$app_root/mocapgate.py" doctor
step 'Проверка компьютера / Computer check'
# Offline mode: no extra network requests during setup. Warnings never fail the install.
preflight=0; run_preflight "$py" "$app_root" 0 || preflight=$?
if [ "$preflight" = 2 ]; then
  echo '[!] Установка завершена, но для части моделей компьютер не готов (см. [X] выше). / Setup finished, but the computer is not ready for some models (see [X] above).'
fi
echo 'Готово: приложение, инструменты и демо-дубль установлены. / Setup complete.'
[ -n "$log" ] && echo "Журнал / Log: $log"
if [ "$skip_launch" = 0 ]; then
  step 'Запуск MoCapGate Studio / Starting MoCapGate Studio'
  if [ -d "$app" ]; then open "$app"; else "$py" "$app_root/mocapgate.py" studio; fi
fi
