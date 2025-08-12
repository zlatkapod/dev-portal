import os
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.responses import HTMLResponse

from env_loader import load_env_from_dotenv
from mr_fetcher import fetch_gitlab_mrs

app = FastAPI(title="Dev Portal")

load_env_from_dotenv(".env.local")
load_env_from_dotenv(".env")

_static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(_static_dir):
    app.mount("/static", StaticFiles(directory=_static_dir), name="static")


@app.get("/", response_class=HTMLResponse)
async def dashboard() -> HTMLResponse:
    # If a static index.html exists, serve it to allow a pure static frontend
    static_index = os.path.join(os.path.dirname(__file__), "static", "index.html")
    if os.path.isfile(static_index):
        try:
            with open(static_index, "r", encoding="utf-8") as f:
                return HTMLResponse(content=f.read())
        except Exception:
            # Fall through to the bundled inline dashboard on any error
            pass


def _filter_mrs(items):
    """
    Keep only MRs that are:
    - state == opened
    - not draft/WIP
    - have reviewers empty (interpreting as "no review yet")
    - authored by someone else (if current_username provided)
    """
    result = []
    for mr in items or []:
        reviewers = mr.get("reviewers")
        if reviewers is None:
            # If field absent, consider unknown -> keep it, but safer to check user_notes_count
            reviewers = []
        if len(reviewers) != 0:
            # There are reviewers assigned; treat as already in review
            continue
        result.append(mr)
    return result


@app.get("/api/widgets/review-mrs")
async def team_review_mrs():
    """
    Returns list of MRs needing review from colleagues, filtered.
    If GitLab env is missing, it falls back to bundled sample data.
    """
    source = "sample"
    username = None
    items = []

    assignees_raw = os.getenv("GITLAB_ASSIGNEES", "").strip()
    base_params: dict[str, object] = {
        "state": "opened",
        "scope": "all",
        "order_by": "updated_at",
        "sort": "desc",
        "per_page": 50,
    }

    try:
        live, username = fetch_gitlab_mrs(assignees_raw, base_params)
        if isinstance(live, list):
            items = live
            source = "gitlab"
    except Exception as e:
        print(e)
        items = []
        source = "sample"

    filtered = _filter_mrs(items)

    normalized = []
    for mr in filtered:
        normalized.append({
            "id": mr.get("id"),
            "iid": mr.get("iid"),
            "title": mr.get("title"),
            "author": mr.get("author"),
            "created_at": mr.get("created_at"),
            "web_url": mr.get("web_url"),
            "state": mr.get("state")
        })

    return JSONResponse({
        "items": normalized,
        "count": len(normalized),
        "source": source,
        "username": username,
        "server_time": datetime.now(timezone.utc).isoformat(),
    })


@app.get("/api/widgets/my-mrs")
async def widget_my_mrs():
    """
    My open MRs assigned to me. Reuses GitLab fetching similar to team_review_mrs.
    Shows: id, link, has_conflicts, age, is_wip, reviewers_count. Sorted by created_at desc.
    """
    source = "sample"
    # Allow overriding via env; default to the requested username
    target_username = os.getenv("MY_MRS_ASSIGNEE", os.getenv("GITLAB_USERNAME", "zlata.podlucka")).strip()

    items = []

    base_params: dict[str, object] = {
        "state": "opened",
        "scope": "all",
        "order_by": "created_at",
        "sort": "desc",
        "per_page": 50,
    }

    try:
        live, _ = fetch_gitlab_mrs(target_username, base_params)
        if isinstance(live, list):
            items = live
            source = "gitlab"
    except Exception as e:
        print(e)
        items = []
        source = "sample"

    # Normalize and compute requested fields
    now = datetime.now(timezone.utc)
    def parse_dt(s: str | None):
        if not s:
            return None
        try:
            # Handle trailing 'Z'
            if s.endswith("Z"):
                s = s[:-1] + "+00:00"
            return datetime.fromisoformat(s)
        except Exception:
            return None

    normalized = []
    for mr in items or []:
        created_at = mr.get("created_at")
        created_dt = parse_dt(created_at)
        age_days = None
        if created_dt is not None:
            delta = now - created_dt
            age_days = max(0, int(delta.total_seconds() // 86400))
        reviewers = mr.get("reviewers") or []
        is_wip = bool(mr.get("draft") or mr.get("work_in_progress"))
        normalized.append({
            "id": mr.get("id"),
            "iid": mr.get("iid"),
            "link": mr.get("web_url"),
            "has_conflicts": mr.get("has_conflicts"),
            "created_at": created_at,
            "age_days": age_days,
            "is_wip": is_wip,
            "reviewers_count": len(reviewers),
        })

    # Ensure sorting by created_at desc if API didn't guarantee
    normalized.sort(key=lambda x: x.get("created_at") or "", reverse=True)

    return JSONResponse({
        "items": normalized,
        "count": len(normalized),
        "source": source,
        "assignee": target_username,
        "server_time": now.isoformat(),
    })


@app.get("/api/widgets/todos")
async def widget_todos():
    """
    Dummy: small todo list for today.
    """
    items = [
        {"id": "t1", "text": "Review MR !11", "done": False},
        {"id": "t2", "text": "Prepare deployment notes", "done": True},
        {"id": "t3", "text": "Check flaky test in CI", "done": False},
    ]
    return JSONResponse({
        "items": items,
        "count": len(items),
        "server_time": datetime.now(timezone.utc).isoformat(),
        "source": "dummy"
    })


@app.post("/api/actions/rebase-all")
async def action_rebase_all():
    """
    Dummy: trigger 'rebase all my MRs'.
    Returns a fake job immediately.
    """
    job = {
        "job_id": "job_dummy_001",
        "status": "queued",
        "queued_at": datetime.now(timezone.utc).isoformat(),
        "estimated_total": 2,
    }
    return JSONResponse(job)
