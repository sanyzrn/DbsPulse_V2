# AGENTS.md

## Cursor Cloud specific instructions

DbsPulse is a two-service app: a FastAPI backend (`backend/`, Python) and a React + Vite frontend (`frontend/`). It needs a PostgreSQL 16 database. Standard setup/run/test commands live in `README.md`; only the non-obvious, cloud-environment caveats are captured here.

### Startup (not handled by the update script)
The update script only refreshes dependencies (`backend/.venv` via `requirements-dev.txt`, and `frontend` via `npm ci`). These must be done manually at the start of a session:

- **Start PostgreSQL** (installed in the snapshot, but not auto-started): `sudo pg_ctlcluster 16 main start`. The `dbspulse` role (password `dbspulse_dev_password`) and the `dbspulse` + `dbspulse_test` databases are created in the snapshot; if they are ever missing, recreate them (see `README.md` DB section and `.github/workflows/ci.yml` for the test DB).
- **Backend env file:** `backend/.env` is git-ignored. If absent, `cp backend/.env.example backend/.env` — its defaults already point at the local Postgres above.
- **Run migrations + seed:** from `backend/` with the venv active, `alembic upgrade head`. This also seeds the 20 indicators and the demo users/personnel. Safe to re-run (idempotent).

### Running the dev servers
- Backend: `cd backend && source .venv/bin/activate && uvicorn app.main:app --reload --port 8000` (serves `/api/*`, docs at `/docs`).
- Frontend: `cd frontend && npm run dev` (Vite on `:5173`, proxies `/api` → `:8000`). Both must run for the UI to work.

### Testing / lint / build
- Backend tests need the `dbspulse_test` database to exist. Run from `backend/` with venv active: `ruff check .` and `pytest`. Tests run in rolled-back transactions, so no cleanup is needed.
- Frontend: `npm run lint` (oxlint — prints non-blocking warnings, exits 0), `npm test` (vitest), `npm run build`.

### Non-obvious gotchas
- Seed login accounts (all password `DbsPulse@12345`): `hr1` (HR), `sup1`/`sup2` (unit supervisors), `dep1` (deputy), `ceo1` (CEO). The full 4-stage approval workflow is described in `README.md`.
- Scoring: entering scores auto-saves them as a draft (`PUT /api/evaluations/{id}/scores`). The separate final-submit button ("ثبت ارزیابی") calls `POST /api/evaluations/{id}/submit`, which **requires every indicator to be scored** and returns a validation error otherwise — a partially-scored evaluation is expected to be rejected at final submit even though the individual draft scores are persisted. A score of 1 or 5 requires an evidence justification of at least 3 words.
- PDF export (WeasyPrint) needs system libs (`libpango*`, `libcairo2`, etc.); these are in the snapshot. Without them the app still works and only the PDF endpoint returns a clear 500.
