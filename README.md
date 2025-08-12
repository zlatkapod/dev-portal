# DevPortal

A lightweight developer dashboard built with FastAPI. It aggregates day-to-day developer signals into simple widgets, with an initial focus on GitLab Merge Requests that may need your review. The UI can be served statically while the backend fetches live data from GitLab when configured.

Note: This project is in an early stage and will be refactored and reorganized. The goal of this README is to help you get oriented and run it quickly.

## What this project does (high level)
- Serves a minimal dashboard (at `/`) showing a list of colleagues’ Merge Requests.
- When GitLab access is configured, fetches MRs using the GitLab REST API and filters them for quick review triage.
- When GitLab is not configured, it falls back to sample/dummy data so you can still see the UI.
- Exposes a few additional dummy widgets and actions that illustrate the intended direction (e.g., "my MRs", todos, unread counters, "rebase all").

## GitLab API reference used
- The project uses the "List merge requests" endpoint as a foundation:
  https://docs.gitlab.com/api/merge_requests/#list-merge-requests

## Environment variables
Create a `.env` file in the project root to configure live GitLab calls. These are read on startup.

Required for live GitLab queries:
- GITLAB_API_URL: Base GitLab API URL, typically ends with `/api/v4`.
  - Example: `https://gitlab.com/api/v4`
- GITLAB_TOKEN: Personal Access Token with sufficient permissions to read merge requests (API scope).
  - Example: `glpat-********************************`

Optional selectors and defaults:
- GITLAB_ASSIGNEES: Comma-separated GitLab usernames to query as assignees. If set, the app will call the MR list endpoint once per username and aggregate results.
  - Example: `alice,bob,charlie`
- GITLAB_USERNAME: Default username fallback; used as the single assignee if `GITLAB_ASSIGNEES` is not provided.
  - Example: `john.doe`

Currently not used (reserved for future features):
- GITLAB_USER_ID: Numeric user ID that may be used by future endpoints or actions.

Behavior notes:
- If GITLAB_API_URL or GITLAB_TOKEN is missing, the backend will not call GitLab and will return sample data instead so the UI remains usable.

## Quick start
Prerequisites:
- Python 3.11+ recommended

Install dependencies (FastAPI and Uvicorn):
- `pip install fastapi uvicorn`

Create `.env` in the project root (see the variables above). Minimal example for live GitLab use:
```
GITLAB_API_URL="https://gitlab.example.com/api/v4"
GITLAB_TOKEN="glpat-XXXXXXXXXXXXXXXX"
GITLAB_ASSIGNEES="alice,bob"
# or use GITLAB_USERNAME if you want to query a single user
# GITLAB_USERNAME="alice"
```

Run the server:
- `uvicorn main:app --reload`

Open the dashboard:
- http://127.0.0.1:8000/

Try widget endpoints (examples):
- Review MRs widget (JSON): `GET http://127.0.0.1:8000/api/widgets/review-mrs`
- My MRs widget (dummy): `GET http://127.0.0.1:8000/api/widgets/my-mrs`
- Todos widget (dummy): `GET http://127.0.0.1:8000/api/widgets/todos`
- Action (dummy): `POST http://127.0.0.1:8000/api/actions/rebase-all`

Tip: The repository includes `test_main.http` with ready-to-run HTTP snippets (usable in many IDEs).

## Orientation and structure
- `main.py` – FastAPI application with a tiny `.env` loader and endpoints. It attempts to query GitLab MRs per assignee username and aggregates results. If env is missing, it serves sample data.
- `static/` – Contains a static dashboard (`index.html`). If present, the app serves it at `/static` and also uses it for the home page if available.
- `static/dummy/gl_mr_res.json` – Sample data for reference.
- `test_main.http` – Handy HTTP requests to exercise the API.

## Security and notes
- Do NOT commit real tokens to version control. Keep `.env` local and out of VCS. Rotate any token that may have been exposed.
- This project is under active refactoring; endpoint names, shapes, and filtering logic may change.
