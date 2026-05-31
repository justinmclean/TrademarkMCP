"""Fetch and cache the ASF project list (committees + podlings).

Uses the stdlib ``urllib`` so the package has no runtime dependencies.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.request
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from apache_trademark_mcp.policy import normalize

COMMITTEES_URL = "https://projects.apache.org/json/foundation/committees.json"
PODLINGS_URL = "https://projects.apache.org/json/foundation/podlings.json"

DEFAULT_CACHE_TTL_SECONDS = 24 * 60 * 60  # 24 hours
DEFAULT_TIMEOUT_SECONDS = 15.0


def default_cache_dir() -> Path:
    """Return the default on-disk cache directory."""
    return Path.home() / ".cache" / "apache-trademark-mcp"


def cache_file(cache_dir: Path) -> Path:
    return cache_dir / "asf_projects.json"


def _load_cache(path: Path, ttl_seconds: int) -> list[dict] | None:
    if not path.exists():
        return None
    age = time.time() - path.stat().st_mtime
    if age > ttl_seconds:
        return None
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    if isinstance(data, list):
        return data
    return None


def _save_cache(path: Path, data: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))


def _http_get_json(url: str, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": "apache-trademark-mcp/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        return json.loads(resp.read().decode("utf-8"))


def _normalize_entries(value: Any) -> list[dict]:
    if isinstance(value, dict):
        return [{"id": k, **v} for k, v in value.items() if isinstance(v, dict)]
    if isinstance(value, list):
        return [entry for entry in value if isinstance(entry, dict)]
    return []


def _merge_projects(committees: list[dict], podlings: list[dict]) -> list[dict]:
    """Combine committees and podlings, deduping by id (case-insensitive).

    Graduated podlings appear in both feeds (e.g. ``hugegraph`` is in
    committees.json as the current TLP and in podlings.json as the historical
    incubator-era entry named ``HugeGraph (Incubating)``). The committee entry
    is authoritative — keep it and drop the duplicate podling row. Podlings
    without a matching committee (current incubation, retired) pass through.
    """
    merged: list[dict] = []
    seen: set[str] = set()

    def _key(entry: dict) -> str:
        return str(entry.get("id", "")).strip().lower()

    for entry in committees:
        key = _key(entry)
        if not key or key in seen:
            continue
        seen.add(key)
        merged.append(entry)

    for entry in podlings:
        key = _key(entry)
        if not key or key in seen:
            continue
        seen.add(key)
        merged.append(entry)

    return merged


def fetch_projects(
    cache_dir: Path | None = None,
    ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS,
    force: bool = False,
) -> list[dict]:
    """Return the combined committees + podlings list (cached for 24h by default).

    Falls back to a stale cache if the network is unavailable. Returns ``[]``
    if nothing is reachable and no cache exists.
    """
    resolved_cache_dir = cache_dir or default_cache_dir()
    path = cache_file(resolved_cache_dir)

    if not force:
        cached = _load_cache(path, ttl_seconds)
        if cached is not None:
            return cached

    try:
        committees = _normalize_entries(_http_get_json(COMMITTEES_URL))
        podlings = _normalize_entries(_http_get_json(PODLINGS_URL))
        data = _merge_projects(committees, podlings)
        _save_cache(path, data)
        return data
    except (urllib.error.URLError, json.JSONDecodeError, OSError):
        # Network unavailable — fall back to whatever stale cache we have.
        if path.exists():
            try:
                stale = json.loads(path.read_text())
                if isinstance(stale, list):
                    return stale
            except (OSError, json.JSONDecodeError):
                pass
        return []


def refresh_cache(cache_dir: Path | None = None) -> dict:
    """Force a fresh fetch and return a status payload."""
    resolved_cache_dir = cache_dir or default_cache_dir()
    path = cache_file(resolved_cache_dir)
    if path.exists():
        try:
            path.unlink()
        except OSError:
            pass
    try:
        committees = _normalize_entries(_http_get_json(COMMITTEES_URL))
        podlings = _normalize_entries(_http_get_json(PODLINGS_URL))
        data = _merge_projects(committees, podlings)
        _save_cache(path, data)
        return {
            "status": "success",
            "projects_loaded": len(data),
            "committees": len(committees),
            "podlings": len(podlings),
            "duplicates_dropped": len(committees) + len(podlings) - len(data),
            "cache_file": str(path),
        }
    except (urllib.error.URLError, json.JSONDecodeError, OSError) as exc:
        return {
            "status": "error",
            "error": str(exc),
            "cache_file": str(path),
            "message": "Failed to fetch project list. Check network access to projects.apache.org.",
        }


def cache_age_hours(cache_dir: Path | None = None) -> float | None:
    """Return the age of the cache file in hours, or ``None`` if absent."""
    path = cache_file(cache_dir or default_cache_dir())
    if not path.exists():
        return None
    return round((time.time() - path.stat().st_mtime) / 3600, 1)


# ---------------------------------------------------------------------------
# Name extraction and similarity
# ---------------------------------------------------------------------------


_INCUBATING_SUFFIX_RE = re.compile(r"\s*\(\s*incubating\s*\)\s*$", re.IGNORECASE)


def _clean_project_name(title: str) -> str:
    """Strip leading ``Apache `` and trailing ``(Incubating)`` from a name."""
    clean = re.sub(r"^apache\s+", "", title, flags=re.IGNORECASE)
    clean = _INCUBATING_SUFFIX_RE.sub("", clean)
    return clean.strip()


def project_names(projects: list[dict]) -> list[str]:
    """Return a flat list of project ids + human names for similarity checks."""
    names: list[str] = []
    for entry in projects:
        if not isinstance(entry, dict):
            continue
        pid = entry.get("id", "")
        if pid:
            names.append(pid)
        title = entry.get("name", "")
        if title:
            clean = _clean_project_name(title)
            if clean and clean.lower() != pid.lower():
                names.append(clean)
    return names


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def _project_url(norm_name: str) -> str:
    return f"https://{norm_name.replace(' ', '-')}.apache.org"


def find_name_conflicts(
    proposed: str,
    projects: list[dict],
    *,
    conflict_threshold: float = 0.90,
    nearby_threshold: float = 0.70,
    max_conflicts: int = 5,
    max_nearby: int = 8,
) -> tuple[list[dict], list[dict]]:
    """Return ``(conflicts, nearby)`` matches against existing ASF projects."""
    norm_proposed = normalize(proposed)
    conflicts: list[dict] = []
    nearby: list[dict] = []
    seen: set[str] = set()

    for proj_name in project_names(projects):
        norm_proj = normalize(proj_name)
        if not norm_proj or norm_proj in seen:
            continue
        seen.add(norm_proj)

        if norm_proposed == norm_proj:
            conflicts.append(
                {
                    "name": proj_name,
                    "similarity": 1.0,
                    "match_type": "exact",
                    "url": _project_url(norm_proj),
                }
            )
            continue

        score = _similarity(norm_proposed, norm_proj)
        if score >= conflict_threshold:
            conflicts.append(
                {
                    "name": proj_name,
                    "similarity": round(score, 2),
                    "match_type": "near_exact",
                    "url": _project_url(norm_proj),
                }
            )
        elif score >= nearby_threshold:
            nearby.append(
                {
                    "name": proj_name,
                    "similarity": round(score, 2),
                    "match_type": "similar",
                    "url": _project_url(norm_proj),
                }
            )

    conflicts.sort(key=lambda x: x["similarity"], reverse=True)
    nearby.sort(key=lambda x: x["similarity"], reverse=True)
    return conflicts[:max_conflicts], nearby[:max_nearby]


def find_similar(
    proposed: str,
    projects: list[dict],
    *,
    threshold: float = 0.50,
    limit: int = 20,
) -> list[dict]:
    """Return projects whose name has similarity >= threshold to ``proposed``."""
    norm_proposed = normalize(proposed)
    seen: set[str] = set()
    results: list[dict] = []

    for proj_name in project_names(projects):
        norm_proj = normalize(proj_name)
        if not norm_proj or norm_proj in seen:
            continue
        seen.add(norm_proj)

        score = _similarity(norm_proposed, norm_proj)
        if score >= threshold:
            results.append(
                {
                    "name": proj_name,
                    "similarity": round(score, 2),
                    "url": _project_url(norm_proj),
                }
            )

    results.sort(key=lambda x: x["similarity"], reverse=True)
    return results[:limit]


def project_descriptions(projects: list[dict]) -> dict[str, str]:
    """Return ``{normalized_id: shortdesc}`` for enriching search results."""
    out: dict[str, str] = {}
    for entry in projects:
        if not isinstance(entry, dict):
            continue
        pid = entry.get("id", "")
        if not pid:
            continue
        out[pid] = entry.get("shortdesc", "") or entry.get("description", "")
    return out


# ---------------------------------------------------------------------------
# Environment overrides (used by tools.configure_defaults)
# ---------------------------------------------------------------------------


def cache_dir_from_env(value: str | None) -> Path:
    """Resolve a cache directory from an explicit value, env var, or default."""
    if value:
        return Path(os.path.expanduser(value))
    env = os.environ.get("APACHE_TRADEMARK_MCP_CACHE_DIR")
    if env:
        return Path(os.path.expanduser(env))
    return default_cache_dir()
