import json
import os
import urllib.parse
import urllib.request


def fetch_gitlab_mrs(assignees_raw: str, params: dict[str, object]):
    """Fetch MRs from GitLab if env is configured; otherwise return None.
    Uses GITLAB_ASSIGNEES env var (comma-separated) or GITLAB_USERNAME to filter by assignees.
    Since GitLab does not support bulk assignee_username queries for our case, call per-user and aggregate.
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

    print(f"Fetching GitLab MRs per assignee (usernames): {', '.join(assignee_usernames)}")

    aggregated: list[dict] = []
    seen_ids: set[int] = set()

    for uname in assignee_usernames:
        params = dict(params)
        params["assignee_username"] = uname
        query = urllib.parse.urlencode(params, doseq=True)
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
            if isinstance(data, list):
                for mr in data:
                    mr_id = mr.get("id")
                    if isinstance(mr_id, int):
                        if mr_id in seen_ids:
                            continue
                        seen_ids.add(mr_id)
                    aggregated.append(mr)

    return aggregated, default_username or None
