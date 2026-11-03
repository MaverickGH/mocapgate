"""GPU/RAM measurement and GEM-X settings advice (stdlib only, never raises).

Used by the Studio host (sample(), parse_model_resource_line(), recommend()) and
imported by the portable GEM-X worker inside WSL/Linux/macOS (memory(),
parse_cuda_version()), so it must stay free of MoCapGate imports, numpy and torch,
and work on Python 3.8+.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import time

_TIMEOUT = 4.0
_WSL_TTL = 5.0
_wsl_cache = {}


def _run(cmd, timeout=_TIMEOUT):
    """Output of a short command or None (missing tool, timeout, error)."""
    try:
        flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0) if os.name == 'nt' else 0
        done = subprocess.run(cmd, capture_output=True, timeout=timeout, creationflags=flags)
        if done.returncode != 0:
            return None
        raw = done.stdout
        # wsl.exe itself prints UTF-16; commands run through --exec print UTF-8
        if raw[:2] in (b'\xff\xfe', b'\xfe\xff') or (len(raw) > 1 and raw[1:2] == b'\x00'):
            return raw.decode('utf-16', 'replace')
        return raw.decode('utf-8', 'replace')
    except (OSError, subprocess.SubprocessError, ValueError):
        return None


def _num(text):
    try:
        value = float(str(text).strip())
    except (TypeError, ValueError):
        return None
    return int(value) if value.is_integer() else value


# ---------------------------------------------------------------- parsers (pure)

def parse_nvidia_smi(text):
    """CSV from `nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu
    --format=csv,noheader,nounits` → [{name, vram_used_mb, vram_total_mb, util}]."""
    gpus = []
    for line in (text or '').splitlines():
        parts = [p.strip() for p in line.split(',')]
        if len(parts) < 4 or not parts[0]:
            continue
        gpus.append({'name': parts[0], 'vram_used_mb': _num(parts[1]),
                     'vram_total_mb': _num(parts[2]), 'util': _num(parts[3])})
    return gpus


def parse_cuda_version(text):
    """Driver's maximum CUDA version from the nvidia-smi header ("CUDA Version: 12.6") → (12, 6)."""
    match = re.search(r'CUDA Version:\s*(\d+)\.(\d+)', text or '')
    return (int(match.group(1)), int(match.group(2))) if match else None


def parse_meminfo(text):
    """/proc/meminfo → {used_mb, total_mb, available_mb} (used = MemTotal − MemAvailable)."""
    values = {}
    for line in (text or '').splitlines():
        key, _, rest = line.partition(':')
        parts = rest.split()
        if parts and parts[0].isdigit():
            values[key.strip()] = int(parts[0]) * (1024 if len(parts) < 2 or parts[1].lower() == 'kb' else 1)
    total = values.get('MemTotal')
    if not total:
        return None
    available = values.get('MemAvailable')
    if available is None:  # very old kernels
        available = values.get('MemFree', 0) + values.get('Buffers', 0) + values.get('Cached', 0)
    mb = 1024 * 1024
    return {'used_mb': (total - available) // mb, 'total_mb': total // mb, 'available_mb': available // mb}


def parse_vm_stat(text, total_bytes):
    """macOS `vm_stat` + hw.memsize → {used_mb, total_mb, available_mb}.

    Available = free + inactive + speculative pages (what macOS can hand out without
    swapping); used = total − available, close to Activity Monitor's "Memory Used"."""
    if not total_bytes:
        return None
    match = re.search(r'page size of (\d+) bytes', text or '')
    page = int(match.group(1)) if match else 4096
    pages = {}
    for line in (text or '').splitlines():
        key, _, value = line.partition(':')
        value = value.strip().rstrip('.')
        if value.isdigit():
            pages[key.strip().lower()] = int(value)
    if not pages:
        return None
    available = page * sum(pages.get(k, 0) for k in ('pages free', 'pages inactive', 'pages speculative'))
    available = min(available, total_bytes)
    mb = 1024 * 1024
    return {'used_mb': (total_bytes - available) // mb, 'total_mb': total_bytes // mb, 'available_mb': available // mb}


_LINE = re.compile(r'INFO\s+\[MoCapGate\]\s+(memory|peak|chunk):\s*(.*)$')


def parse_model_resource_line(line):
    """`INFO [MoCapGate] memory|peak|chunk: k=v …` from the GEM-X worker → dict or None.

    Numbers become int/float, `None`/`-` become None, other values stay strings.
    The result carries the line kind under "kind"."""
    match = _LINE.search(str(line or '').strip())
    if not match:
        return None
    out = {'kind': match.group(1)}
    for key, value in re.findall(r'([A-Za-z_][\w]*)=(\S*)', match.group(2)):
        if value in ('None', '-', ''):
            out[key] = None
        else:
            number = _num(value)
            out[key] = value if number is None else number
    return out


# ---------------------------------------------------------------- probes

def gpus():
    """NVIDIA GPUs via nvidia-smi on this machine (on Windows the host driver also covers WSL)."""
    smi = shutil.which('nvidia-smi')
    if not smi and os.path.exists('/usr/lib/wsl/lib/nvidia-smi'):
        smi = '/usr/lib/wsl/lib/nvidia-smi'
    if not smi:
        return None
    out = _run([smi, '--query-gpu=name,memory.used,memory.total,utilization.gpu', '--format=csv,noheader,nounits'])
    return parse_nvidia_smi(out) if out else None


def driver_cuda_version():
    """Maximum CUDA version of the NVIDIA driver, e.g. (12, 6), or None."""
    smi = shutil.which('nvidia-smi') or ('/usr/lib/wsl/lib/nvidia-smi' if os.path.exists('/usr/lib/wsl/lib/nvidia-smi') else None)
    return parse_cuda_version(_run([smi])) if smi else None


def _windows_memory():
    import ctypes

    class Status(ctypes.Structure):
        _fields_ = [('dwLength', ctypes.c_ulong), ('dwMemoryLoad', ctypes.c_ulong),
                    ('ullTotalPhys', ctypes.c_ulonglong), ('ullAvailPhys', ctypes.c_ulonglong),
                    ('ullTotalPageFile', ctypes.c_ulonglong), ('ullAvailPageFile', ctypes.c_ulonglong),
                    ('ullTotalVirtual', ctypes.c_ulonglong), ('ullAvailVirtual', ctypes.c_ulonglong),
                    ('ullAvailExtendedVirtual', ctypes.c_ulonglong)]
    status = Status()
    status.dwLength = ctypes.sizeof(Status)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return None
    mb = 1024 * 1024
    return {'used_mb': (status.ullTotalPhys - status.ullAvailPhys) // mb,
            'total_mb': status.ullTotalPhys // mb, 'available_mb': status.ullAvailPhys // mb}


def memory():
    """System RAM of the current OS (inside WSL: the WSL VM) → {used_mb, total_mb, available_mb} or None."""
    try:
        if os.name == 'nt':
            return _windows_memory()
        if sys.platform == 'darwin':
            total = _num((_run(['sysctl', '-n', 'hw.memsize']) or '').strip())
            return parse_vm_stat(_run(['vm_stat']), total)
        with open('/proc/meminfo', encoding='utf-8') as source:
            return parse_meminfo(source.read())
    except Exception:  # noqa: BLE001 — measurement must never break processing
        return None


def wsl_memory(distro):
    """Memory of a WSL distro (`wsl.exe -d <distro> --exec cat /proc/meminfo`), cached a few seconds."""
    if os.name != 'nt' or not distro:
        return None
    now = time.monotonic()
    hit = _wsl_cache.get(distro)
    if hit and now - hit[0] < _WSL_TTL:
        return hit[1]
    value = parse_meminfo(_run(['wsl.exe', '-d', str(distro), '--exec', 'cat', '/proc/meminfo'], timeout=3.0))
    _wsl_cache[distro] = (now, value)
    return value


def sample(cfg=None):
    """Snapshot for the Studio: {gpu, ram_used_mb, ram_total_mb, wsl_ram_used_mb, wsl_ram_total_mb}.

    cfg may name the WSL distro under gemx_wsl / gvhmr_wsl. Missing parts are None."""
    out = {'gpu': None, 'ram_used_mb': None, 'ram_total_mb': None, 'wsl_ram_used_mb': None, 'wsl_ram_total_mb': None}
    try:
        out['gpu'] = gpus()
    except Exception:  # noqa: BLE001
        pass
    ram = memory()
    if ram:
        out['ram_used_mb'], out['ram_total_mb'] = ram['used_mb'], ram['total_mb']
    try:
        distro = (cfg or {}).get('gemx_wsl') or (cfg or {}).get('gvhmr_wsl')
        wsl = wsl_memory(distro) if distro else None
    except Exception:  # noqa: BLE001
        wsl = None
    if wsl:
        out['wsl_ram_used_mb'], out['wsl_ram_total_mb'] = wsl['used_mb'], wsl['total_mb']
    return out


# ---------------------------------------------------------------- advice

def recommend(peaks, totals=None):
    """Benchmark result → suggested GEM-X settings for this machine.

    peaks: the worker's benchmark JSON (or its "resources"): vram_mb, ram_mb, rss_mb,
    vram_total_mb, ram_total_mb, fps_processing, people. totals: optional machine totals
    (vram_total_mb, ram_total_mb; e.g. from sample()) that override the worker's.

    Heuristic (the benchmark clip is short, so the measured peak is mostly the models):
    headroom = 1 − max(peak VRAM / total VRAM, peak RAM / total RAM).
      quality: "fast" without CUDA, with < 10 GB VRAM or headroom < 35 %; "max" only with
      ≥ 20 GB VRAM, headroom ≥ 60 % and ≥ 10 processed frames/s; otherwise "accurate".
      chunk_seconds: 0 (off) with headroom ≥ 50 % and ≥ 12 GB VRAM and ≥ 32 GB RAM;
      60 with headroom ≥ 30 %; 30 with ≥ 15 %; else 15.
      max_people: by speed per person (fps_processing × people): ≥ 8 → 4, ≥ 3 → 2, else 1;
      at most 2 when headroom < 30 %.
    """
    peaks = dict(peaks or {})
    if isinstance(peaks.get('resources'), dict):  # whole benchmark JSON: flatten its peaks
        peaks = {**peaks, **peaks['resources']}
    source = dict(peaks)
    for key, value in (totals or {}).items():
        if value is not None:
            source[key] = value
    if totals and totals.get('gpu') and not source.get('vram_total_mb'):
        first = totals['gpu'][0] if totals['gpu'] else {}
        source['vram_total_mb'] = first.get('vram_total_mb')
    if totals and totals.get('wsl_ram_total_mb'):
        source['ram_total_mb'] = totals['wsl_ram_total_mb']  # GEM-X runs inside the WSL VM

    def ratio(used, total):
        try:
            return float(used) / float(total) if used is not None and total else None
        except (TypeError, ValueError, ZeroDivisionError):
            return None
    vram_total = source.get('vram_total_mb')
    ram_total = source.get('ram_total_mb')
    vram_ratio = ratio(peaks.get('vram_mb'), vram_total)
    ram_ratio = ratio(peaks.get('ram_mb') if peaks.get('ram_mb') is not None else peaks.get('rss_mb'), ram_total)
    used = [r for r in (vram_ratio, ram_ratio) if r is not None]
    headroom = 1.0 - max(used) if used else 0.0
    fps = float(peaks.get('fps_processing') or source.get('fps_processing') or 0.0)
    people = max(1, int(peaks.get('people') or source.get('people') or 1))
    per_person = fps * people
    cuda = bool(vram_total)

    if not cuda or (vram_total or 0) < 10000 or headroom < 0.35:
        quality = 'fast'
    elif vram_total >= 20000 and headroom >= 0.6 and fps >= 10:
        quality = 'max'
    else:
        quality = 'accurate'
    if headroom >= 0.5 and (vram_total or 0) >= 12000 and (ram_total or 0) >= 32000:
        chunk = 0
    elif headroom >= 0.3:
        chunk = 60
    elif headroom >= 0.15:
        chunk = 30
    else:
        chunk = 15
    max_people = 4 if per_person >= 8 else 2 if per_person >= 3 else 1
    if headroom < 0.3:
        max_people = min(max_people, 2)

    pct = int(round(headroom * 100))
    vram_text = f'{int(vram_total)} MB VRAM' if vram_total else 'no CUDA GPU'
    ram_text = f'{int(ram_total)} MB RAM' if ram_total else 'unknown RAM'
    chunk_en = 'off' if chunk == 0 else f'{chunk} s'
    chunk_ru = 'без разбиения' if chunk == 0 else f'по {chunk} с'
    reason = {
        'en': (f'{vram_text}, {ram_text}; memory headroom {pct}% at the benchmark peak; '
               f'{fps:.1f} frames/s for {people} people. Quality {quality}, chunks {chunk_en}, up to {max_people} people.'),
        'ru': (f'{vram_text.replace("no CUDA GPU", "нет CUDA GPU")}, {ram_text.replace("unknown RAM", "RAM неизвестна")}; '
               f'запас памяти {pct}% на пике теста; {fps:.1f} кадр/с для {people} чел. '
               f'Качество {quality}, фрагменты {chunk_ru}, до {max_people} чел.'),
    }
    return {'quality': quality, 'chunk_seconds': chunk, 'max_people': max_people, 'reason': reason}
