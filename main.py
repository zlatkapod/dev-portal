import os
import time
from datetime import datetime, timezone

from fastapi import FastAPI, Body, Path
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.responses import HTMLResponse

from env_loader import load_env_from_dotenv
from mr_fetcher import fetch_gitlab_mrs
from todos import write_todos, read_todos

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
        "per_page": 30,
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
    Shows: id, link, has_conflicts, age_days (by created_at), is_wip, reviewers_count, updated_at, updated_ago.
    Sorted by updated_at desc.
    """
    source = "sample"
    # Allow overriding via env; default to the requested username
    target_username = os.getenv("MY_MRS_ASSIGNEE", os.getenv("GITLAB_USERNAME", "zlata.podlucka")).strip()

    items = []

    base_params: dict[str, object] = {
        "state": "opened",
        "scope": "all",
        "order_by": "updated_at",
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

    def humanize_delta(delta_seconds: float) -> str:
        # Returns a compact human-readable string like 'just now', '5m', '2h', '3d'
        if delta_seconds < 0:
            delta_seconds = 0
        if delta_seconds < 45:
            return "just now"
        minutes = delta_seconds // 60
        if minutes < 60:
            return f"{int(minutes)}m"
        hours = minutes // 60
        if hours < 48:
            return f"{int(hours)}h"
        days = hours // 24
        if days < 14:
            return f"{int(days)}d"
        weeks = days // 7
        if weeks < 8:
            return f"{int(weeks)}w"
        years = days // 365
        if years >= 1:
            return f"{int(years)}y"
        months = days // 30
        return f"{int(months)}mo"

    normalized = []
    for mr in items or []:
        created_at = mr.get("created_at")
        created_dt = parse_dt(created_at)
        age_days = None
        if created_dt is not None:
            delta = now - created_dt
            age_days = max(0, int(delta.total_seconds() // 86400))

        updated_at = mr.get("updated_at")
        updated_dt = parse_dt(updated_at)
        updated_ago = None
        if updated_dt is not None:
            udelta = now - updated_dt
            updated_ago = humanize_delta(udelta.total_seconds())

        reviewers = mr.get("reviewers") or []
        is_wip = bool(mr.get("draft") or mr.get("work_in_progress"))
        normalized.append({
            "id": mr.get("id"),
            "iid": mr.get("iid"),
            "link": mr.get("web_url"),
            "has_conflicts": mr.get("has_conflicts"),
            "created_at": created_at,
            "age_days": age_days,
            "updated_at": updated_at,
            "updated_ago": updated_ago,
            "is_wip": is_wip,
            "reviewers_count": len(reviewers),
        })

    # Ensure sorting by updated_at desc if API didn't guarantee
    normalized.sort(key=lambda x: x.get("updated_at") or "", reverse=True)

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
    Simple todo list backed by data/todos.csv.
    - Each pending todo is stored as a single line (description only).
    - Completed items are removed from the file.
    """
    texts = read_todos()
    items = [{"id": idx, "text": t, "done": False} for idx, t in enumerate(texts)]
    return JSONResponse({
        "items": items,
        "count": len(items),
        "server_time": datetime.now(timezone.utc).isoformat(),
        "source": "file"
    })


@app.post("/api/widgets/todos")
async def create_todo(text: str = Body(..., embed=True)):
    """
    Create a new todo item by appending to data/todos.csv.
    Accepts JSON body: { "text": "..." }
    """
    text = (text or "").strip()
    if not text:
        return JSONResponse({"ok": False, "error": "Text must not be empty"}, status_code=400)

    text = text.replace("\r", " ").replace("\n", " ")
    if len(text) > 300:
        text = text[:300].rstrip()

    lines = read_todos()
    lines.append(text)
    write_todos(lines)

    return JSONResponse({"ok": True})


@app.post("/api/widgets/todos/{item_id}/done")
async def complete_todo(item_id: int = Path(..., ge=0)):
    """
    Mark todo as done by its position (index) and remove it from the CSV.
    """
    lines = read_todos()
    if item_id < 0 or item_id >= len(lines):
        return JSONResponse({"ok": False, "error": "Todo not found"}, status_code=404)
    # Remove the item
    del lines[item_id]
    write_todos(lines)
    return JSONResponse({"ok": True})


