"""Resumable verified downloads and self-healing environments (stdlib only).

Also imported by scripts/setup_gvhmr.py and scripts/setup_gemx.py inside WSL/Linux,
so this module must stay free of MoCapGate imports and work on Python 3.8+.
"""
import hashlib
import http.client
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request

AGENT = 'Mozilla/5.0 MoCapGate/0.3.3'
ATTEMPTS = 3


class IncompleteDownload(OSError):
    """Connection closed before the announced length; the .part file is kept for resume."""


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def _transfer(url, part, size, log, timeout, label):
    offset = part.stat().st_size if part.exists() else 0
    if size and offset > size:
        part.unlink()
        offset = 0
    if size and offset == size:
        return
    headers = {'User-Agent': AGENT}
    if offset:
        headers['Range'] = 'bytes=%d-' % offset
    try:
        response = urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=timeout)
    except urllib.error.HTTPError as exc:
        if exc.code == 416 and offset:
            return  # уже скачано целиком; проверка ниже решит, годится ли файл
        raise
    with response:
        status = getattr(response, 'status', None) or 200
        if offset and (status != 206 or not str(response.headers.get('Content-Range') or '').startswith('bytes %d-' % offset)):
            offset = 0  # сервер не поддержал докачку — начинаем заново
        length = int(response.headers.get('Content-Length') or 0)
        total = offset + length if length else (size or 0)
        received = offset
        reported = -1
        started = time.monotonic()
        with part.open('ab' if offset else 'wb') as output:
            while True:
                block = response.read(1024 * 1024)
                if not block:
                    break
                output.write(block)
                received += len(block)
                if size and received > size:
                    raise ValueError('%s: размер больше ожидаемого' % label)
                step = received * 10 // total if total else received // (50 * 1024 * 1024)
                if step != reported:
                    reported = step
                    elapsed = max(1e-3, time.monotonic() - started)
                    speed = (received - offset) / elapsed  # байт/с в этой попытке (докачка не завышает скорость)
                    eta = (total - received) / speed if total and speed > 0 else None
                    log('%s: %d MB' % (label, received // (1024 * 1024)) + (' / %d MB' % (total // (1024 * 1024)) if total else '')
                        + (' · %.1f MB/s' % (speed / 1048576) if elapsed > 1 else '')
                        + (' · осталось ~%d:%02d' % divmod(int(eta), 60) if eta is not None and elapsed > 1 else ''))
        if length and received - offset < length:
            raise IncompleteDownload('соединение прервано на %d MB' % (received // (1024 * 1024)))


def fetch(url, destination, digest=None, size=None, log=print, check=None, timeout=60, attempts=ATTEMPTS, label=None):
    """Download to <name>.part with Range resume and retries; verify, then rename.

    A failed checksum or check() deletes the partial file; a network failure keeps it so
    the next attempt (or the next setup run) continues where it stopped."""
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    part = destination.with_name(destination.name + '.part')
    label = label or destination.name
    for attempt in range(1, attempts + 1):
        try:
            _transfer(url, part, size, log, timeout, label)
            break
        except urllib.error.HTTPError as exc:
            if exc.code < 500 and exc.code not in (408, 429) or attempt == attempts:
                raise RuntimeError('%s: сервер ответил HTTP %d' % (label, exc.code)) from exc
            error = exc
        except ValueError:
            part.unlink(missing_ok=True)
            raise
        except (OSError, EOFError, http.client.HTTPException) as exc:  # URLError, таймаут, обрыв
            if attempt == attempts:
                raise RuntimeError('%s: загрузка прервана (%s). Повторите установку — она продолжит скачивание.'
                                   % (label, getattr(exc, 'reason', None) or exc or type(exc).__name__)) from exc
            error = exc
        log('%s: сбой сети (%s), повтор %d/%d…' % (label, getattr(error, 'reason', None) or error, attempt + 1, attempts))
        time.sleep(2 ** attempt)
    try:
        if size and part.stat().st_size != size:
            raise ValueError('%s: неверный размер файла' % label)
        if digest and sha256(part) != digest:
            raise ValueError('SHA256 mismatch: ' + destination.name)
        if check:
            check(part)
    except BaseException:
        part.unlink(missing_ok=True)
        raise
    part.replace(destination)
    return destination


def python_works(python):
    try:
        return subprocess.run([str(python), '-c', 'import sys'], capture_output=True, timeout=120).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def ensure_venv(directory, create, log=print):
    """Recreate an environment whose interpreter is missing or broken (interrupted setup,
    removed base Python). create() builds a fresh one in the now-empty directory."""
    directory = Path(directory)
    python = directory / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if python_works(python):
        return python
    if python.exists():
        try:  # отвечает слишком долго (антивирус, холодный WSL) — не повод удалять окружение на гигабайты
            subprocess.run([str(python), '-c', 'import sys'], capture_output=True, timeout=300)
        except subprocess.TimeoutExpired:
            raise RuntimeError('Python окружения не отвечает: ' + str(python) + '. Перезапустите компьютер и повторите установку.')
        except (OSError, subprocess.SubprocessError):
            pass
    if directory.exists():
        log('Окружение Python повреждено или не завершено — пересоздаю: ' + str(directory))
        shutil.rmtree(directory)
    create()
    if not python_works(python):
        raise RuntimeError('Не удалось создать окружение Python: ' + str(directory))
    return python


def host_python(version):
    """Use the running interpreter for uv venv when it matches, so uv never downloads Python."""
    return sys.executable if sys.executable and '%d.%d' % sys.version_info[:2] == version else version


def clone(url, repo, run):
    """Remove an interrupted clone (no valid HEAD) before cloning again."""
    repo = Path(repo).resolve()
    if repo == repo.parent:
        raise ValueError('Repository directory cannot be a filesystem root')
    if repo.exists():
        broken = not (repo / '.git').exists() or subprocess.run(
            ['git', '--git-dir', str(repo / '.git'), 'rev-parse', '--verify', '-q', 'HEAD'], capture_output=True).returncode != 0
        if broken:
            print('Удаляю незавершённую копию репозитория: ' + str(repo), flush=True)
            shutil.rmtree(repo)
    if not repo.exists():
        run('git', 'clone', url, repo)
