# Weekwise

**Plan your week. Make progress every day.**

Weekwise is a standalone, responsive study-planning web application for students. It helps you organize courses and assignments, break work into tasks, plan study time, recognize overload, and choose an actionable next task. Weekwise is designed to run **independently of a university LMS**. Optional LMS account linking and academic-data import are planned, not implemented.

## Current functionality

- **Accounts:** Register, sign in, and keep your own planning records separate from other users.
- **Today:** See deadlines and a suggested next task with an explanation.
- **Courses and assignments:** Create personal courses and assignments, edit them, archive courses without deleting their assignments, and review approaching or overdue deadlines.
- **Tasks:** Add, edit, reorder, complete, reopen, or delete tasks attached to assignments; view assignment progress.
- **Dependencies:** Define optional prerequisites *within the same assignment*. The app rejects self-references, cross-assignment dependencies, and cycles.
- **Priority guidance:** Prioritize assignments by due date (overdue first); within an assignment, suggest a ready task according to its prerequisites and the student's task order. Blocked tasks are explained. Effort estimates do not override dependency order.
- **Weekly planner:** Set daily study availability, schedule task durations, and see overload warnings. Unknown availability is different from zero available hours.
- **Backup & restore:** Export personal planning records to JSON, validate a backup, and explicitly confirm restoration. Restoring **replaces** the current account's planning records; it does not merge them.
- **Interface:** Responsive Today, My Work, and Planner views with light/dark appearance options. Developer sprint and user-story labels are not shown to students.

**Scope:** The above reflects the Sprint 1 and Sprint 2 implementation and dependency patch. Study invitations, saved opportunities, and advanced connection features are planned for the next increment.

## Requirements

- Python **3.11+**
- Node.js **20+** and npm
- Git Bash on Windows (commands below) or an equivalent shell
- Optional: Docker and Docker Compose for PostgreSQL

## Run locally

### 1. Start the API

From the project root:

```bash
cd backend
python -m venv venv           # first setup only
source venv/Scripts/activate
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8001
```

API documentation: <http://127.0.0.1:8001/docs>

Weekwise defaults to SQLite for local development. When started from `backend/`, its database is `backend/weekwise.db`. Keep that file if you want to retain your accounts and study data. The starter initializes missing tables automatically for local development.

### 2. Start the frontend

In a second terminal, from the project root:

```bash
cd frontend
npm install                   # first setup only
npm run dev -- --port 5174
```

Open <http://localhost:5174>. Register a Weekwise account or sign in with an existing one.

**Important — API proxy:** The original starter's `frontend/vite.config.ts` proxies `/api` to port **8000**. Because the commands above use **8001** to avoid conflicts with the University LMS, update its proxy target to `http://127.0.0.1:8001` before running the frontend. If you keep the original proxy on 8000, you must instead run the Weekwise API on 8000 with no competing service.

### 3. Optional PostgreSQL

The included `docker-compose.yml` provides PostgreSQL on local port **5433**:

```bash
docker compose up -d db
```

Configure `DATABASE_URL` in the backend environment, for example:

```text
postgresql+psycopg://weekwise:weekwise_dev_password@localhost:5433/weekwise
```

The credentials above are **development-only**. Do not use them in production. SQLite and PostgreSQL are separate data stores; changing `DATABASE_URL` does not automatically migrate existing data.

## Test and build

From `backend/` with the virtual environment active:

```bash
python -m pytest -q
```

From `frontend/`:

```bash
npm run build
```

The dependency update was checked against **17 passing backend tests** in the prepared patch baseline. Re-run tests locally after installing patches or making changes. Full browser-based end-to-end and accessibility regression coverage still needs to be completed and recorded before treating the release as finished.

## How priority works

1. Ignore completed tasks and assignments with no remaining work.
2. Rank assignments by their deadline, with overdue work first.
3. Within each assignment, distinguish **ready** tasks from tasks **blocked by unfinished prerequisites**.
4. Recommend the first ready task by the student's task order.
5. Explain the choice and any blocking prerequisites; do not automatically reschedule or complete tasks.

Dependencies are only between tasks **inside the same assignment**. Separate assignments compete by their own deadlines. A missing effort estimate is *unknown*, not zero.

## Backup safety

Open **Backup & Restore** in the application to export or restore planning records. Backups can contain assignment names, notes, tasks, schedules, and dependencies, so keep them private. Export a fresh backup **before** trying restoration. Restoration requires confirmation and may assign new record IDs. Invalid or incompatible files must be rejected without partial replacement. A source-code rollback does not undo a completed data restore.

## Project structure

```text
weekwise-starter/
├── backend/
│   ├── app/                 # FastAPI, auth, persistence, planning, guidance
│   ├── tests/               # Backend regression tests
│   └── requirements.txt
├── frontend/
│   ├── src/                 # React / TypeScript UI
│   ├── package.json
│   └── vite.config.ts
├── docs/                     # Project and implementation documentation
├── docker-compose.yml       # Optional development PostgreSQL
└── README.md
```

## Known limitations and next steps

- **No LMS integration yet:** Weekwise accounts and personal courses work independently; LMS single sign-on, course imports, and synchronization remain future work.
- **No production-ready authentication deployment:** Add secure HTTPS deployment, secret management, session/cookie hardening, email verification or recovery, and rate limiting before public use.
- **No formal production migrations yet:** Automatic table creation is intended for local development. Introduce Alembic migrations before deploying to a shared or production database.
- **Sprint 3 is planned:** Invitation drafting/sharing, saved opportunity management/filtering, and further explained guidance. Optional product-backlog features are not part of the current implementation.
- **Release verification remains:** Confirm cross-browser behavior, responsive layouts, keyboard accessibility, data persistence, and the complete regression suite on the actual installed version.

## Project and contribution notes

Weekwise follows the Agile Practices and Processes project plan for Team 5Guys. User-story IDs and sprint tracking belong in the backlog and development documentation, not in the everyday student interface. Keep credentials, local `.env` files, virtual environments, databases, and generated build artifacts out of Git. Record actual test results and releases rather than assuming a planned increment has been accepted.
