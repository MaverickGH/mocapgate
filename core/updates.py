"""MoCapGate — проверка новой версии Studio по релизам GitHub (MaverickGH/app-releases, теги mocapgate-v…).

Запрос анонимный: никаких данных о пользователе или дублях не уходит. Ответ кэшируется на 6 часов;
нет сети — просто «обновлений не найдено». Только stdlib.
"""
from __future__ import annotations
import json
import re
import time
import urllib.request

RELEASES = "https://api.github.com/repos/MaverickGH/app-releases/releases?per_page=40"
PAGE = "https://github.com/MaverickGH/app-releases/releases/tag/"
TTL = 6 * 3600
_cache: dict = {}


def parse(version: str) -> tuple:
    """«0.3.3-beta.6» → (0, 3, 3, 0, 6); финальный 0.3.3 → (0, 3, 3, 1, 0) — старше любой беты."""
    m = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)(?:-(?:beta|rc|alpha)\.?(\d+))?", version.strip())
    if not m:
        return ()
    major, minor, patch, pre = m.groups()
    return (int(major), int(minor), int(patch), 0 if pre else 1, int(pre or 0))


def newest(releases: list, prefix: str = "mocapgate-v") -> dict | None:
    best = None
    for r in releases:
        tag = r.get("tag_name") or ""
        if r.get("draft") or not tag.startswith(prefix) or not parse(tag[len(prefix):]):
            continue
        if best is None or parse(tag[len(prefix):]) > parse(best["tag_name"][len(prefix):]):
            best = r
    return best


def check(current: str, fetch=None, now=None) -> dict:
    """→ {available, version, url, name} или {available: False, error?}."""
    now = time.time() if now is None else now
    if _cache.get("at", -TTL) > now - TTL and _cache.get("current") == current:
        return _cache["result"]
    try:
        if fetch is None:
            request = urllib.request.Request(RELEASES, headers={"Accept": "application/vnd.github+json",
                                                                "User-Agent": "MoCapGate-Studio"})
            with urllib.request.urlopen(request, timeout=8) as response:
                releases = json.loads(response.read().decode("utf-8"))
        else:
            releases = fetch()
        best = newest(releases)
        version = best["tag_name"][len("mocapgate-v"):] if best else ""
        result = {"available": bool(best) and parse(version) > parse(current), "current": current,
                  "version": version, "url": PAGE + best["tag_name"] if best else "", "name": (best or {}).get("name", "")}
    except (OSError, ValueError, KeyError, TypeError) as exc:
        result = {"available": False, "current": current, "error": type(exc).__name__}
    _cache.update(at=now, current=current, result=result)
    return result
