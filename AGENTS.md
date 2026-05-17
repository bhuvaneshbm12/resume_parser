# AGENTS.md

Guidance for future Codex sessions working in this repository.

## Project Overview

This is a FastAPI resume parser backed by Postgres, Redis, Celery, and Gemini, with a Next.js frontend in `frontend/`.

Main flow:
- `GET /health` returns `{"status": "ok", "version": "...", "timestamp": "..."}` and is used by `verify.sh`.
- `POST /parse` accepts a PDF upload.
- `routers/parse.py` extracts text with PyPDF2, stores a `resumes` row with status `pending`, and enqueues `parse_resume_task`.
- `workers/tasks.py` reads the resume text, calls Gemini `gemini-2.5-flash`, validates the response with `ParsedResume`, inserts into `parsed_fields`, and updates status to `done` or `failed`.
- `GET /results/{task_id}` returns `{status}` until status is `done`, then returns parsed fields.

Core files:
- `main.py` - FastAPI app and lifespan setup.
- `database.py` - asyncpg pool and table creation from SQLAlchemy metadata.
- `logging_config.py` - application logging setup for console and `logs/app.log`.
- `models.py` - SQLAlchemy table metadata for `resumes` and `parsed_fields`.
- `schemas.py` - Pydantic v2 `ParsedResume` schema.
- `routers/parse.py` - API endpoints.
- `workers/tasks.py` - Celery task and Gemini parsing logic.
- `workers/celery_config.py` - Celery configuration module loaded via `config_from_object`.
- `workers/monitor.py` - Redis/Celery queue status helper.
- `docker-compose.yml` - API, worker, Redis, and Postgres services.
- `frontend/` - Next.js 14 App Router frontend.
- `verify.sh` - end-to-end golden path verifier.
- `test_resume.pdf` - committed text-based fictional PDF fixture for `verify.sh`.

## Local Environment

Required environment variables:
- `DATABASE_URL`
- `REDIS_URL`
- `GEMINI_API_KEY`
- `GEMINI_MODEL`, default should remain `gemini-2.5-flash`

Additional app configuration:
- `LOG_LEVEL`, default `INFO`
- `MAX_FILE_SIZE_MB`, default `5`
- `APP_VERSION`, default `1.0.0`
- `OPENAI_API_KEY` exists in `.env.example` as a future-provider placeholder; current worker code still uses Gemini.
- Frontend uses `NEXT_PUBLIC_API_URL`, defaulting in code to `http://localhost:8000`.

Use `.env.example` as the template. Never commit `.env`.

Important Docker hostname rule:
- Inside Docker Compose, use `postgres` and `redis` hostnames.
- From host Windows Python, those names may not resolve. Helper scripts include fallbacks for common cases, but app containers should continue using Docker service names.

Windows Python notes:
- Docker runs Python 3.12; host Windows may have a different default Python.
- Python 3.12.10 has been installed locally at `C:\Users\bhuva\AppData\Local\Programs\Python\Python312\python.exe`.
- Git Bash may not have a working `python3`; it can be missing or point to the Microsoft Store alias. Prefer `py -3.12`, `python`, or the full Python 3.12 path when running ad hoc host commands.
- `verify.sh` intentionally discovers a working Python command and does not require `jq`.

## Docker Networking Rules

Treat container networking and host networking as different environments.

Inside Compose services:
- API and worker must use `DATABASE_URL=postgresql://postgres:postgres@postgres:5432/resumes`.
- API and worker must use `REDIS_URL=redis://redis:6379/0`.
- Do not change service-to-service URLs to `localhost`; inside a container, `localhost` points to that same container.

From the host machine:
- Browser and curl should use `http://localhost:8000`.
- Host Python may need `postgres` rewritten to `localhost` for direct DB access.
- Host Python may need `redis` rewritten to `localhost` for direct Redis access.
- Prefer `docker compose exec -T api python check_db.py` for DB inspection because it uses the same network and environment as the deployed API.

Compose dependencies:
- `worker` must wait for Redis health with `condition: service_healthy`.
- `api` may use `service_started`, because it owns DB startup table creation and can fail loudly if Postgres is not ready.
- Redis healthcheck must stay in exec form: `["CMD", "redis-cli", "ping"]`.

When debugging networking:

```bash
docker compose ps
docker compose logs --tail=80 redis
docker compose exec -T api python check_db.py
docker compose exec -T worker python workers/monitor.py
```

## Common Commands

Start the stack:

```bash
docker compose up -d
```

Restart after code changes:

```bash
docker compose restart api worker
```

Check worker logs:

```bash
docker compose logs --tail=120 worker
```

Check API logs:

```bash
docker compose logs --tail=120 api
```

Run the golden path verifier:

```bash
./verify.sh
```

Validate Python syntax:

```bash
python -m compileall main.py database.py models.py schemas.py routers workers check_db.py test_llm.py test_schema.py logging_config.py
```

Inspect DB from inside Docker:

```bash
docker compose exec -T api python check_db.py
```

Monitor queue state:

```bash
python workers/monitor.py
```

Test Gemini prompt manually:

```bash
python test_llm.py
```

Test schema validation:

```bash
python test_schema.py
```

Frontend build:

```bash
cd frontend
npm install
npm run build
```

Run frontend locally:

```bash
cd frontend
npm run dev
```

Pretty-print JSON from Git Bash on this Windows machine:

```bash
curl -s http://localhost:8000/health | "/c/Users/bhuva/AppData/Local/Programs/Python/Python312/python.exe" -m json.tool
```

## API Usage

Health check:

```bash
curl -s http://localhost:8000/health
```

Upload a PDF:

```bash
curl -s -X POST http://localhost:8000/parse -F "file=@test_resume.pdf"
```

Poll results:

```bash
curl -s http://localhost:8000/results/<task_id>
```

Expected non-final statuses include `pending`, `processing`, and `failed`.
Final successful status is `done`.

API error response standards:
- Missing upload file on `POST /parse` returns HTTP 422 with `{"detail":"no file provided"}`.
- Non-PDF uploads return HTTP 415 with `{"detail":"only PDF files are accepted"}`.
- Files larger than `MAX_FILE_SIZE_MB` return HTTP 413 with `{"detail":"file too large, maximum size is 5MB"}` when the default 5 MB limit is active.
- PyPDF2 extraction exceptions return HTTP 422 with `{"detail":"could not extract text from PDF"}`.
- Readable PDFs with too little extracted text return HTTP 400 with `{"detail":"the PDF could not be read"}`.
- Unknown task id on `GET /results/{task_id}` returns HTTP 404 with `{"detail":"task not found"}`.

Manual upload with pretty JSON from PowerShell:

```powershell
curl.exe -s -X POST http://localhost:8000/parse -F "file=@test_resume.pdf" |
  & "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe" -m json.tool
```

Manual upload with pretty JSON from Git Bash:

```bash
curl -s -X POST http://localhost:8000/parse -F "file=@test_resume.pdf" \
  | "/c/Users/bhuva/AppData/Local/Programs/Python/Python312/python.exe" -m json.tool
```

## Worker and Retry Behavior

`workers/tasks.py` uses Gemini through `google-genai`.

Celery retry standards:
- Gemini 429 client errors are converted to `gemini.RateLimitError`.
- Timeout exceptions are converted to `gemini.APITimeoutError`.
- Celery task decorator uses:
  - `autoretry_for=(gemini.RateLimitError, gemini.APITimeoutError)`
  - `max_retries=3`
  - `retry_backoff=10`
  - `soft_time_limit=60`
  - `time_limit=70`
- Do not autoretry schema validation errors, invalid JSON, missing DB rows, or permanent configuration errors.
- Retry only transient external API failures: rate limits, request timeouts, and similar retry-safe failures.
- Keep `task_acks_late=True` and `worker_prefetch_multiplier=1` in `workers/celery_config.py` so crashed workers do not silently lose queued jobs and each worker process reserves only one task at a time.
- Any exception that should trigger Celery autoretry must escape the task function as one of the classes listed in `autoretry_for`.
- Do not swallow retryable exceptions in `run_parse_resume`; logging is fine, but the exception must be re-raised.
- Final failure after retries should set `resumes.status` to `failed` and include `resume_id` in the log line.

Timeout standards:
- The soft timeout is 60 seconds and should mark the resume as `failed` with error message `timeout`.
- The hard timeout is 70 seconds and exists as a process-kill fallback.
- Never leave `time.sleep(...)` timeout probes in committed code.

Do not leave temporary retry or timeout test code in `workers/tasks.py`.
Before committing, always search for:

```bash
Select-String -Path workers\tasks.py -Pattern "time.sleep", "simulated", "RateLimitError"
```

Only `RateLimitError` references that are part of the compatibility classes and Celery decorator should remain.

## Gemini API Handling

The active model is `gemini-2.5-flash`. Keep defaults aligned across:
- `.env.example`
- `workers/tasks.py`
- `test_llm.py`

Prompt contract:
- Gemini should return JSON only, no markdown and no backticks.
- Still strip code fences defensively because models can return fenced JSON despite instructions.
- Preserve `strip_json_code_fence()` unless replacing it with stricter JSON extraction.

Response handling standards:
- Parse raw Gemini text with `json.loads(strip_json_code_fence(content))`.
- Normalize missing values before Pydantic validation:
  - `name` and `email`: `None` -> `""`
  - `skills`, `experience`, `education`: `None` -> `[]`
- Validate with `ParsedResume.model_validate(...)` before writing to DB.
- Validation failure should mark `resumes.status` as `failed` and return early, not retry.
- Invalid JSON should be treated as a model response problem; log the raw parsing failure carefully without dumping sensitive resume text.

Gemini SDK caveat:
- `google-genai` does not expose OpenAI-style `RateLimitError` and `APITimeoutError` classes.
- This project currently defines compatibility classes under a local `gemini` namespace so the Celery decorator can use the requested shape.
- If upgrading the SDK, check the actual error class names before changing `autoretry_for`.

Do not log full resume text or API keys. Logs should include `resume_id`, status transitions, retry count, and exception summaries.

## Data Contracts

`ParsedResume` requires:

```python
name: str
email: str
skills: list[str]
experience: list[dict]
education: list[dict]
```

Gemini can return `null` for missing fields. `normalize_resume_payload()` converts:
- missing string fields to `""`
- missing array fields to `[]`

Keep this normalization unless the schema is changed to allow optional values.

`parsed_fields.skills`, `experience`, and `education` are stored as Postgres `jsonb`.
`routers/parse.py` uses `decode_jsonb()` because asyncpg can return JSONB values as strings depending on connection setup.

## API Runtime Behavior

`main.py` includes production-readiness middleware and handlers:
- `CORSMiddleware` is enabled with all origins, methods, and headers allowed. Lock this down before a real public deployment.
- `RequestLoggingMiddleware` logs method, path, status code, and response time in milliseconds. It uses `time.time()` before and after `await call_next(request)`.
- A global `@app.exception_handler(Exception)` logs unhandled exceptions with traceback and returns clean JSON: `{"error":"internal server error","detail": str(exc)}` with HTTP 500.
- Temporary crash-test routes such as `/crash` must not be committed.

`logging_config.py`:
- Configures Python logging with `LOG_LEVEL` defaulting to `INFO`.
- Uses format `timestamp | level | module | message`.
- Writes to console and `logs/app.log`.
- `logs/app.log` is ignored by the existing `*.log` rule and should not be committed.

`database.py`:
- Uses asyncpg pool sizing `min_size=2`, `max_size=10`.
- On startup, `main.py` calls `connect_db()`, `check_database_connection()`, then `init_db()`.
- `check_database_connection()` runs `SELECT 1`.
- Pool initialization and startup check failures log `CRITICAL` with the database URL included but password masked as `***`, then raise `SystemExit(1)` so Docker restarts the API container.
- Never log an unmasked `DATABASE_URL`.

## Frontend

The frontend is a Next.js 14 App Router app under `frontend/`.

Core frontend files:
- `frontend/app/layout.tsx` - root layout, Tailwind globals, centered max-width `2xl` shell, `Resume Parser` header.
- `frontend/app/page.tsx` - server component rendering `UploadForm` inside a card.
- `frontend/app/results/[taskId]/page.tsx` - server component passing `taskId` to `ResultsDisplay`.
- `frontend/components/UploadForm.tsx` - client component for PDF upload and redirect to `/results/{taskId}`.
- `frontend/components/ResultsDisplay.tsx` - client component that polls `/results/{taskId}` every 3 seconds and stops when status is `done` or `failed`.
- `frontend/lib/api.ts` - API helper using `NEXT_PUBLIC_API_URL || "http://localhost:8000"`.
- `frontend/components/ui/` - shadcn-style `badge`, `button`, `card`, and local `spinner` components.

Frontend package notes:
- Current Next version is `14.2.35`.
- `npm run build` has passed.
- `package-lock.json` should be committed with `package.json`.
- `frontend/node_modules/`, `frontend/.next/`, and `frontend/out/` are ignored and must not be committed.

Tailwind/shadcn notes:
- shadcn added `@import "tw-animate-css";` and `@import "shadcn/tailwind.css";` in `frontend/app/globals.css`.
- `frontend/tailwind.config.js` must define shadcn CSS-variable color tokens such as `border`, `ring`, `background`, `foreground`, `card`, `primary`, `muted`, etc.
- The previous build error `The border-border class does not exist` was fixed by adding those theme tokens.
- The previous build error for `outline-ring/50` was fixed by removing the incompatible global `@apply outline-ring/50` from `globals.css`.
- `layout.tsx` should not import `Geist` from `next/font/google`; this setup uses the system font stack.
- If TypeScript complains about `.next/types/**/*.ts` after deleting `.next/`, run `npm run build` or `npm run dev` once to regenerate Next type files.

Frontend API/CORS notes:
- The backend already has `CORSMiddleware` allowing all origins, methods, and headers. If the browser still reports CORS, restart the API container so it loads current `main.py`.
- `next.config.js` exposes `NEXT_PUBLIC_API_URL` through `env`.
- Docker Compose sets frontend `NEXT_PUBLIC_API_URL=http://localhost:8000`, which is correct for browser-side calls from the user’s machine.

Recent frontend updates:
- `frontend/lib/api.ts` now exposes `uploadResume(file)` for `POST /parse` and `getResults(taskId)` for `GET /results/{taskId}`. Upload errors are normalized to `File too large` for 413, `Only PDFs accepted` for 415, and `Upload failed` otherwise. Unknown result ids throw `Result not found`.
- `frontend/components/UploadForm.tsx` shows the selected filename, disables the upload button while uploading, displays `Uploading...`, redirects to `/results/{taskId}` on success, and shows API error messages in a red box.
- `frontend/components/ResultsDisplay.tsx` polls immediately and every 3 seconds, clears intervals on completion/unmount, renders pending/processing with a spinner, and renders request failures or backend `failed` status as the red failed card with a retry button.
- `ResultsDisplay` defensively handles `skills` returned either as a JSON array or as a JSON string, because asyncpg/jsonb behavior can vary.
- The results card uses shadcn-style `Card`, `Badge`, and local `Separator` components, with contact, skills, experience, and education sections.
- `frontend/components/ui/separator.tsx` is a local shadcn-style separator helper.
- `frontend/app/results/[taskId]/page.tsx` stringifies the route param and includes a back button linking to `/`.
- `npm.cmd run build` passed after these frontend changes. On Windows PowerShell, prefer `npm.cmd` if the `npm.ps1` shim is blocked by execution policy.

## Docker Compose Notes

Redis healthcheck should stay in exec form:

```yaml
healthcheck:
  test: ["CMD", "redis-cli", "ping"]
  interval: 5s
  timeout: 3s
  retries: 3
```

Worker should depend on Redis health:

```yaml
depends_on:
  postgres:
    condition: service_started
  redis:
    condition: service_healthy
```

Both `api` and `worker` should use `restart: unless-stopped`.

The `frontend` service:

```yaml
frontend:
  build:
    context: ./frontend
    dockerfile: Dockerfile
  restart: unless-stopped
  environment:
    NEXT_PUBLIC_API_URL: http://localhost:8000
  ports:
    - "3000:3000"
  depends_on:
    - api
```

`frontend/Dockerfile` uses `node:20-alpine`, runs `npm install`, `npm run build`, exposes `3000`, and starts with `npm start`.
`frontend/.dockerignore` excludes `node_modules`, `.next`, `out`, npm logs, and env files.

`docker compose build frontend` has passed. `docker compose up -d frontend` can fail if host port `3000` is already occupied by a local Node process. Check with:

```powershell
netstat -ano | Select-String ":3000"
```

The API container does not run Uvicorn with reload. After editing `main.py` or routes, restart the API before testing new endpoints:

```bash
docker compose restart api
```

When `/health` returned 404 during debugging, the cause was an already-running API container that had not loaded the new `main.py`; restarting `api` fixed it.

When testing DB startup failure:

```bash
docker compose stop postgres
docker compose restart api
docker compose logs api | Select-String -Pattern "CRITICAL"
docker compose start postgres
docker compose restart api
```

Expected CRITICAL message includes `Database pool initialization failed database_url=postgresql://postgres:***@postgres:5432/resumes` or `Database startup check failed ...`.

After editing `docker-compose.yml`, always run:

```bash
docker compose config
```

If `docker compose config` renders the Redis healthcheck as `CMD-SHELL`, it is probably wrong for this repo. It should render as separate `CMD`, `redis-cli`, and `ping` entries.

## Debugging Workflows

Golden path verifier:

```bash
./verify.sh
```

Expected behavior:
- Check `GET /health` returns HTTP 200.
- Upload `test_resume.pdf`.
- Extract `task_id` using Python JSON parsing, not `jq`.
- Poll `/results/{task_id}` every 3 seconds for up to 60 seconds.
- Print `OK` only when status is `done` and all required fields are present.

`verify.sh` failure modes:
- `FAIL: API health check returned HTTP ...` usually means the API is down, the port is not published, or the API container needs restart after a code change.
- `FAIL: parse response was not valid JSON` can happen if the Python command used for JSON parsing is broken. On Windows/Git Bash, check for the Microsoft Store `python3` alias problem.
- `FAIL: timeout waiting for result` requires checking worker logs, DB status, and Redis queue state.
- If `verify.sh` appears to parse the wrong person, confirm `test_resume.pdf` has not been overwritten with another local PDF.

Failed `/results/{task_id}` response:

1. Query the API:

```bash
curl -s http://localhost:8000/results/<task_id>
```

2. Check worker logs for that exact resume id:

```bash
docker compose logs --tail=200 worker
```

3. Inspect rows from inside Docker:

```bash
docker compose exec -T api python check_db.py
```

Common root causes:
- The API container was not restarted after adding or changing a route.
- `test_resume.pdf` was overwritten by another PDF.
- The local PDF is image-based or otherwise yields empty text from PyPDF2.
- The uploaded file exceeded `MAX_FILE_SIZE_MB`.
- The uploaded file had the wrong `content_type`.
- Gemini returned `null` for a required string before normalization.
- Gemini returned invalid JSON or fenced JSON.
- Gemini returned `503 UNAVAILABLE` or 429 due to demand/rate limits.
- Worker was not restarted after code changes.
- `.env` is missing `GEMINI_API_KEY`, `DATABASE_URL`, or `REDIS_URL`.
- `DATABASE_URL` uses `postgres`, but the script is being run from host Python instead of inside Docker.

Queue debugging:

```bash
python workers/monitor.py
docker compose exec -T worker python workers/monitor.py
```

If pending tasks do not move:
- Confirm Redis health is healthy with `docker compose ps`.
- Confirm the worker is running and connected to `redis://redis:6379/0`.
- Confirm the task name in logs is `workers.tasks.parse_resume_task`.
- Restart the worker after task-code changes.

Schema debugging:

```bash
python test_schema.py
```

LLM prompt debugging:

```bash
python test_llm.py
```

Use `test_llm.py` only when a valid `GEMINI_API_KEY` is configured and a live API call is intended.

Test PDF fixture:
- `test_resume.pdf` is a committed exception to the usual no-PDF rule. It is fictional and safe to keep in the repo.
- It must be text-based, not image-based, so `PyPDF2` can extract text.
- Current expected content is Alex Johnson, `alex@example.com`, skills `Python`, `FastAPI`, `PostgreSQL`, Acme Corp Backend Engineer for 2 years, and BSc Computer Science from University of Mumbai 2022.
- If recreated, verify extraction before using it:

```bash
python -c "from PyPDF2 import PdfReader; text='\n'.join(page.extract_text() or '' for page in PdfReader('test_resume.pdf').pages); print(text); assert 'Alex Johnson' in text and 'alex@example.com' in text"
```

ReportLab was used locally to recreate the fixture as a text PDF, but it is not an app runtime dependency.

## Git and Secrets

`.gitignore` should exclude:
- `.env`
- virtual environments
- Python caches
- PDFs
- local DB files

Do not commit:
- API keys
- `.env`
- `venv/`
- uploaded resumes or sample PDFs, except the committed fictional `test_resume.pdf` fixture
- generated `__pycache__/`

The local `.env` has previously contained a Gemini key. If it appears in output or commits, rotate it immediately.

`.gitattributes` marks `*.pdf` as binary so `test_resume.pdf` is not line-ending converted by Git.

Recent pushed commit:
- `02482d5 Add end-to-end verification script` added `/health`, `verify.sh`, `test_resume.pdf`, `.gitattributes`, and API error handling for missing files / unknown task ids.

## Coding Style

Keep changes small and consistent with the existing simple module layout.

Project conventions:
- Use `asyncpg` for runtime DB operations.
- Use SQLAlchemy only for table metadata and startup DDL.
- Use Pydantic v2 APIs like `model_validate`.
- Keep Gemini prompt changes synchronized between `workers/tasks.py` and `test_llm.py` when applicable.
- Prefer explicit status strings already used by the app: `pending`, `processing`, `done`, `failed`.
- Do not introduce migrations unless asked; current startup uses `CreateTable(..., if_not_exists=True)`.

## Verification Checklist

Before finishing a code change:
- Run `python -m compileall` on touched Python files.
- For Docker/Compose changes, run `docker compose config`.
- For worker changes, restart the worker before testing: `docker compose restart worker`.
- For API route changes, restart the API before testing: `docker compose restart api`.
- If testing `/parse`, check worker logs for task exceptions.
- If testing `/results`, confirm arrays are returned as JSON arrays, not JSON-encoded strings.
