# AGENTS.md

Guidance for future Codex sessions working in this repository.

## Project Overview

This is a FastAPI resume parser backed by Postgres, Redis, Celery, and Gemini.

Main flow:
- `POST /parse` accepts a PDF upload.
- `routers/parse.py` extracts text with PyPDF2, stores a `resumes` row with status `pending`, and enqueues `parse_resume_task`.
- `workers/tasks.py` reads the resume text, calls Gemini `gemini-2.5-flash`, validates the response with `ParsedResume`, inserts into `parsed_fields`, and updates status to `done` or `failed`.
- `GET /results/{task_id}` returns `{status}` until status is `done`, then returns parsed fields.

Core files:
- `main.py` - FastAPI app and lifespan setup.
- `database.py` - asyncpg pool and table creation from SQLAlchemy metadata.
- `models.py` - SQLAlchemy table metadata for `resumes` and `parsed_fields`.
- `schemas.py` - Pydantic v2 `ParsedResume` schema.
- `routers/parse.py` - API endpoints.
- `workers/tasks.py` - Celery task and Gemini parsing logic.
- `workers/celery_config.py` - Celery configuration module loaded via `config_from_object`.
- `workers/monitor.py` - Redis/Celery queue status helper.
- `docker-compose.yml` - API, worker, Redis, and Postgres services.

## Local Environment

Required environment variables:
- `DATABASE_URL`
- `REDIS_URL`
- `GEMINI_API_KEY`
- `GEMINI_MODEL`, default should remain `gemini-2.5-flash`

Use `.env.example` as the template. Never commit `.env`.

Important Docker hostname rule:
- Inside Docker Compose, use `postgres` and `redis` hostnames.
- From host Windows Python, those names may not resolve. Helper scripts include fallbacks for common cases, but app containers should continue using Docker service names.

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

Validate Python syntax:

```bash
python -m compileall main.py database.py models.py schemas.py routers workers check_db.py test_llm.py test_schema.py
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

## API Usage

Upload a PDF:

```bash
curl -s -X POST http://localhost:8000/parse -F "file=@Resume.pdf"
```

Poll results:

```bash
curl -s http://localhost:8000/results/<task_id>
```

Expected non-final statuses include `pending`, `processing`, and `failed`.
Final successful status is `done`.

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

After editing `docker-compose.yml`, always run:

```bash
docker compose config
```

If `docker compose config` renders the Redis healthcheck as `CMD-SHELL`, it is probably wrong for this repo. It should render as separate `CMD`, `redis-cli`, and `ping` entries.

## Debugging Workflows

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
- uploaded resumes or sample PDFs
- generated `__pycache__/`

The local `.env` has previously contained a Gemini key. If it appears in output or commits, rotate it immediately.

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
