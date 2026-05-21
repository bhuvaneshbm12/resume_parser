# Resume Parser

FastAPI and Next.js resume parser that accepts a PDF, extracts text, parses structured resume fields with Gemini, and stores results in Postgres.

## Architecture

```text
PDF upload
   |
   v
Next.js Frontend ---> FastAPI /parse ---> Redis queue ---> Celery worker ---> Gemini 2.5 Flash
                          |                                      |
                          v                                      v
                     Postgres resumes <------------------- parsed_fields
                          |
                          v
                 FastAPI /results/{taskId}
                          |
                          v
                    Next.js results UI
```

## Prerequisites

- Python 3.12
- Node 20
- Docker and Docker Compose
- Gemini API key

## Local Setup

```bash
cp .env.example .env
docker compose up -d --build
curl -s http://localhost:8000/health
cd frontend && npm install
npm run dev
```

## Environment Variables

| Variable | Description |
| --- | --- |
| `DATABASE_URL` | Postgres connection string. Use `postgres` hostname inside Docker Compose. |
| `REDIS_URL` | Redis broker/result backend URL. Use `redis` hostname inside Docker Compose. |
| `GEMINI_API_KEY` | Gemini API key used by the Celery worker. |
| `GEMINI_MODEL` | Gemini model name. Default: `gemini-2.5-flash`. |
| `ALLOWED_ORIGINS` | Comma-separated CORS origins. Default: `*`. |
| `LOG_LEVEL` | Python logging level. Default: `INFO`. |
| `MAX_FILE_SIZE_MB` | Maximum accepted upload size. Default: `5`. |
| `APP_VERSION` | Version returned by `/health`. Default: `1.0.0`. |
| `NEXT_PUBLIC_API_URL` | Frontend API base URL. Local default: `http://localhost:8000`. |

## API Reference

### `POST /parse`

Uploads a PDF resume and queues parsing.

```bash
curl -s -X POST http://localhost:8000/parse \
  -F "file=@test_resume.pdf"
```

Example response:

```json
{
  "task_id": "08f6b7e2-3428-4a90-b26e-e0f11a3dce90"
}
```

Common errors:

```json
{"detail":"only PDF files are accepted"}
```

```json
{"detail":"file too large, maximum size is 5MB"}
```

### `GET /results/{taskId}`

Returns task status until parsing is complete.

```bash
curl -s http://localhost:8000/results/08f6b7e2-3428-4a90-b26e-e0f11a3dce90
```

Pending response:

```json
{
  "status": "processing"
}
```

Completed response:

```json
{
  "status": "done",
  "name": "Alex Johnson",
  "email": "alex@example.com",
  "skills": ["Python", "FastAPI", "PostgreSQL"],
  "experience": [
    {
      "company": "Acme Corp",
      "role": "Backend Engineer",
      "duration": "2 years"
    }
  ],
  "education": [
    {
      "institution": "University of Mumbai",
      "degree": "BSc Computer Science",
      "year": "2022"
    }
  ]
}
```

### `GET /metrics`

Returns operational counters and average parse time.

```bash
curl -s http://localhost:8000/metrics
```

## Verification

Run the full local verifier:

```bash
./verify.sh
```

Run only health checks and the golden path:

```bash
./verify.sh --quick
```

Run against deployed services:

```bash
./verify.sh --prod
```

Run compact CI output:

```bash
./verify.sh --ci
```

## Deployment

- API: Railway - `https://web-production-9d5d8.up.railway.app`
- Frontend: Vercel - `https://resume-parser-khaki-theta.vercel.app`

Set Railway variables for both API and worker services:

```text
DATABASE_URL
REDIS_URL
GEMINI_API_KEY
GEMINI_MODEL=gemini-2.5-flash
ALLOWED_ORIGINS=https://resume-parser-khaki-theta.vercel.app
LOG_LEVEL=INFO
APP_VERSION=1.0.0
CELERY_CONCURRENCY=1
```

Railway commands are defined in `Procfile`:

```text
web: uvicorn main:app --host 0.0.0.0 --port $PORT
worker: celery -A workers.tasks worker --loglevel=info --concurrency=${CELERY_CONCURRENCY:-1}
```

## Known Limitations

- PDF extraction uses PyPDF2, so image-only or scanned resumes may not parse.
- Parsing quality depends on Gemini response quality and rate limits.
- There is no user authentication or upload history UI.
- CORS defaults to `*`; set `ALLOWED_ORIGINS` before public deployment.
- The app uses startup DDL instead of migrations.
