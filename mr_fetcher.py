import json
import os
import time
import urllib.parse
import urllib.request
from typing import Any

# Simple in-process cache to avoid hammering GitLab on repeated requests
# Key: (api_url, assignee_username, frozen_params)
# Value: {"ts": float, "data": list[dict]}
_CACHE: dict[tuple[str, str, tuple[tuple[str, Any], ...]], dict[str, Any]] = {}
_LAST_REQUEST_TS: float | None = None


def _now() -> float:
    return time.monotonic()


def _throttle(min_interval_ms: int):
    global _LAST_REQUEST_TS
    if min_interval_ms <= 0:
        return
    now = _now()
    if _LAST_REQUEST_TS is None:
        _LAST_REQUEST_TS = now
        return
    elapsed = (now - _LAST_REQUEST_TS) * 1000.0
    if elapsed < min_interval_ms:
        time.sleep((min_interval_ms - elapsed) / 1000.0)
    _LAST_REQUEST_TS = _now()


def fetch_gitlab_mrs(assignees_raw: str, params: dict[str, object]):
    """Fetch MRs from GitLab if env is configured; otherwise return None.
    Uses GITLAB_ASSIGNEES env var (comma-separated) or GITLAB_USERNAME to filter by assignees.
    Since GitLab does not support bulk assignee_username queries for our case, call per-user and aggregate.

    Performance safeguards:
    - In-process TTL cache (GITLAB_CACHE_TTL_SECONDS, default 30s) per assignee+params.
    - Min interval between outbound requests (GITLAB_MIN_INTERVAL_MS, default 200ms).
    - Cap per_page to 100 and number of assignees via GITLAB_MAX_ASSIGNEES (default 10).
    """
    api_url = os.getenv("GITLAB_API_URL")
    token = os.getenv("GITLAB_TOKEN")
    if not api_url or not token:
        return None, None

    default_username = os.getenv("GITLAB_USERNAME", "").strip()

    assignee_usernames: list[str] = []
    if assignees_raw:
        assignee_usernames = [a.strip() for a in assignees_raw.split(",") if a.strip()]
    elif default_username:
        assignee_usernames = [default_username]

    if not assignee_usernames:
        return [], default_username or None

    # Cap number of assignees to avoid burst fan-out
    try:
        max_assignees = int(os.getenv("GITLAB_MAX_ASSIGNEES", "10"))
    except Exception:
        max_assignees = 10
    if max_assignees > 0 and len(assignee_usernames) > max_assignees:
        assignee_usernames = assignee_usernames[:max_assignees]

    print(f"Fetching GitLab MRs per assignee (usernames): {', '.join(assignee_usernames)}")

    # Enforce per_page upper bound 100
    safe_params = dict(params or {})
    try:
        per_page = int(safe_params.get("per_page", 20))
    except Exception:
        per_page = 20
    if per_page > 40:
        per_page = 40
    if per_page <= 0:
        per_page = 20
    safe_params["per_page"] = per_page

    aggregated: list[dict] = []
    seen_ids: set[int] = set()

    # Cache TTL and request pacing
    try:
        cache_ttl = int(os.getenv("GITLAB_CACHE_TTL_SECONDS", "30"))
    except Exception:
        cache_ttl = 30
    try:
        min_interval_ms = int(os.getenv("GITLAB_MIN_INTERVAL_MS", "200"))
    except Exception:
        min_interval_ms = 200

    for uname in assignee_usernames:
        one_params = dict(safe_params)
        one_params["assignee_username"] = uname
        # Freeze params for cache key: sorted by key
        frozen_params = tuple(sorted((k, json.dumps(v, sort_keys=True)) for k, v in one_params.items()))
        cache_key = (api_url.rstrip("/"), uname, frozen_params)

        # Serve from cache if fresh
        entry = _CACHE.get(cache_key)
        if entry and (_now() - entry.get("ts", 0)) <= cache_ttl:
            data = entry.get("data") or []
        else:
            # Throttle between outbound requests
            _throttle(min_interval_ms)

            query = urllib.parse.urlencode(one_params, doseq=True)
            url = f"{api_url.rstrip('/')}/merge_requests?{query}"

            req = urllib.request.Request(url)
            req.add_header("PRIVATE-TOKEN", token)
            req.add_header("Accept", "application/json")

            with urllib.request.urlopen(req, timeout=30) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"GitLab API returned HTTP {resp.status} for assignee {uname}")
                body = resp.read()
                try:
                    data = json.loads(body)
                except Exception:
                    data = []
            # Update cache
            _CACHE[cache_key] = {"ts": _now(), "data": data}

        if isinstance(data, list):
            for mr in data:
                mr_id = mr.get("id")
                if isinstance(mr_id, int):
                    if mr_id in seen_ids:
                        continue
                    seen_ids.add(mr_id)
                aggregated.append(mr)

    return aggregated, default_username or None
