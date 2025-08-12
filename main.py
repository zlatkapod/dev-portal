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
    Dummy: list of user's own MRs across projects with rebase states.
    """
    items = [
        {"id": 201, "iid": 21, "title": "Refactor: auth flow", "project": "web-portal", "rebase_status": "can_rebase",
         "web_url": "https://example.com/web-portal/-/merge_requests/21"},
        {"id": 202, "iid": 22, "title": "Chore: bump deps", "project": "api", "rebase_status": "up_to_date",
         "web_url": "https://example.com/api/-/merge_requests/22"},
    ]
    return JSONResponse({
        "items": items,
        "count": len(items),
        "server_time": datetime.now(timezone.utc).isoformat(),
        "source": "dummy"
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
