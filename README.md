# Dev Portal — lightweight developer dashboard with FastAPI

Dev Portal is a small, pragmatic dashboard that aggregates everyday developer signals into simple widgets. It’s built on FastAPI and serves a minimal static UI from `/static/index.html` with JSON endpoints per widget. When GitLab configuration is present, it fetches live data; otherwise endpoints return empty/dummy-friendly results so the UI stays usable.

## What it’s for
- Quickly see teammates’ Merge Requests that need review
- Glance at your own open MRs and basic state (age, conflicts, WIP, reviewers)
- Keep a tiny “today” todo list backed by a CSV file

## Features
- Dashboard at `/` (served from `static/index.html` if present; otherwise an inline HTML page)
- Static files served under `/static`
- Widget APIs:
  - `GET /api/widgets/review-mrs` — live GitLab fetch (when configured), filtered to MRs that need review; normalized payload
  - `GET /api/widgets/my-mrs` — live GitLab fetch (when configured), normalized with extra fields like `age_days`, `reviewers_count`, `has_conflicts`
  - `GET /api/widgets/todos` — returns simple list read from `data/todos.csv`
  - `POST /api/widgets/todos` — add a todo item `{ "text": "..." }`
  - `POST /api/widgets/todos/{id}/done` — mark todo as done (removes it from the CSV)
- GitLab MR fetching strategy:
  - Calls the Merge Requests API once per assignee username, aggregates, and de-duplicates by MR `id`
  - Returns a consistent, minimal JSON shape for the UI
- Environment-driven configuration with precedence:
  1) Process/OS environment (highest)
  2) `.env.local` (your private, real settings; not committed)
  3) `.env` (dummy defaults; committed)

## Configuration
Environment variables are loaded by a minimal loader that does NOT override already-set OS variables. Put real secrets only in your shell/session or in `.env.local` (which is ignored by git). The tracked `.env` contains safe dummy placeholders.

Common variables:
- `GITLAB_API_URL` — Base GitLab API URL (ends with `/api/v4`), e.g. `https://gitlab.com/api/v4`
- `GITLAB_TOKEN` — Personal Access Token with API scope
- `GITLAB_ASSIGNEES` — Comma-separated GitLab usernames to fetch as assignees (aggregated server-side)
- `GITLAB_USERNAME` — Default username fallback if `GITLAB_ASSIGNEES` is empty
- `MY_MRS_ASSIGNEE` — Optional override for the user targeted by `my-mrs` (defaults to `GITLAB_USERNAME`)

Example `.env` (dummy values only):
```
GITLAB_API_URL="https://gitlab.com/api/v4"
GITLAB_TOKEN="dummy-token-change-me"
GITLAB_USERNAME="john.doe"
# If set, takes precedence over GITLAB_USERNAME in fetcher
GITLAB_ASSIGNEES="alice,bob,charlie"
```
Notes:
- If `GITLAB_API_URL` or `GITLAB_TOKEN` is missing, endpoints dependent on GitLab return empty or sample-friendly responses; the UI will display “Sample data”.
- For multiple assignees, the app queries per user and aggregates results server-side.

## Quick start

Prerequisites:
- Python 3.10+

Install dependencies:
```
pip install fastapi uvicorn
```

Run the app (development):
```
uvicorn main:app --reload
```
The dashboard will be available at http://127.0.0.1:8000/

Test endpoints (optional):
- Use the `http_requests.http` file with your IDE HTTP client, or curl the endpoints listed above.

## Development notes
- Static UI is located at `static/index.html`. If the file is removed, the app serves a minimal inline dashboard.
- Todos are stored line-by-line in `data/todos.csv`. Completed items are removed.

## Security and secrets
- A proper `.gitignore` is included to ignore `.env` and `.env.local`. Keep real tokens in environment variables or `.env.local` only.
- The tracked `.env` file contains sanitized dummy placeholders; do not put real secrets there.
- If you previously committed real secrets, rotate them immediately.
