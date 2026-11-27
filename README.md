# Vehicle Maintenance Assistant

A vehicle maintenance assistant with a React frontend, FastAPI backend, and
PostgreSQL vehicle-management API.

## Configure PostgreSQL

Copy `backend/.env.example` to `backend/.env` and set `SECRET_KEY` to a
generated random value. Keep `.env` private because it contains credentials and
the JWT signing key.

Generate a signing key locally with:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

### Option A — Supabase (recommended for cloud-hosted database)

Create a project on [Supabase](https://supabase.com), copy the connection string
from **Settings → Database → Connection string → URI**, and set `DATABASE_URL`
in `backend/.env`:

```
DATABASE_URL=postgresql+psycopg2://postgres.YOUR_PROJECT_REF:YOUR_PASSWORD@aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres
```

Replace the region, project ref, and password with your Supabase project values.
Supabase manages backups, connection pooling, and high availability.

### Option B — Local PostgreSQL

Create a PostgreSQL database named `vehicle_maintenance`, then update
`DATABASE_URL` in `backend/.env` with the username, password, host, and port for
your local installation:

```
DATABASE_URL=postgresql+psycopg2://postgres:YOUR_PASSWORD@localhost:5432/vehicle_maintenance
```

For example, create the database from `psql` or pgAdmin:

```sql
CREATE DATABASE vehicle_maintenance;
```

## Run locally

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

If upgrading a Step 2 database that already has `vehicles` but has no Alembic
revision, stamp the existing schema once:

```powershell
alembic stamp 0001_vehicle
```

The baseline stamp records the existing table without changing its rows. Skip
this stamp for a new database or a database that already has an Alembic revision.
Then apply pending migrations and start the API:

```powershell
alembic current
alembic upgrade head
uvicorn app.main:app --reload
```

The new migration adds nullable `vehicles.user_id` and creates `users`,
`service_records`, `documents`, and `expenses`. New databases are built from the
baseline and architecture migrations. Swagger UI is at
<http://127.0.0.1:8000/docs>. `/health` is a liveness endpoint;
`/ready` checks PostgreSQL and Redis and returns `503` until both are available.
Each API response includes an `X-Request-ID`. Request logs are JSON and exclude
request bodies; validation and internal errors do not echo submitted values or
exception details.

## React frontend

In another terminal, install the frontend dependencies and start Vite:

```powershell
cd frontend
npm install
Copy-Item .env.example .env
npm run dev
```

The frontend is available at <http://localhost:5173> and uses
`VITE_API_URL=http://localhost:8000` by default. Change that variable in
`frontend/.env` if the API runs at another address. The backend's default
`CORS_ORIGINS` already allows the local Vite origins; configure it to include
the frontend origin when using a different host or port.

The authenticated interface includes vehicle management, service history,
expense analytics, document uploads, maintenance predictions, reminders,
notifications, the web-sourced maintenance assistant, and AI mechanic
conversations.

## Vehicle API

- `POST /vehicles/` — register a vehicle
- `GET /vehicles/` — list vehicles
- `GET /vehicles/{vehicle_id}` — get vehicle details
- `PUT /vehicles/{vehicle_id}` — update vehicle information
- `DELETE /vehicles/{vehicle_id}` — delete a vehicle

Vehicle registration numbers are unique. Vehicle years must be between 1900 and
2100, and odometer readings cannot be negative.

## Authentication

- `POST /auth/register` creates an account and stores an Argon2 password hash.
- `POST /auth/login` accepts OAuth2 form fields (`username` is the email) and
  returns a short-lived JWT.
- `GET /auth/me` returns the authenticated account.

All vehicle endpoints require a bearer token. Use **Authorize** in Swagger after
logging in. Vehicle reads and updates are scoped to the current account; requests
for another user's vehicle return 404. Existing vehicles with no `user_id` stay
unassigned and are not exposed to any account until their ownership is confirmed
and explicitly assigned.

## Document uploads

`POST /vehicles/{vehicle_id}/documents/` accepts a multipart `file` and optional
`document_type` field. It supports PDF, JPG, JPEG, and PNG files up to 10 MiB.
The upload must belong to a vehicle owned by the authenticated user. Files are
signature-checked and stored under `backend/uploads/documents/` with generated
names; the original name and detected MIME type are saved as metadata. Storage
is private and is not exposed as a static web directory.

## PDF text extraction

`app.services.invoice_text_extractor.extract_pdf_text(file_path)` extracts
digital text from a stored PDF in `backend/uploads/documents/`. It returns
per-page text and marks pages with fewer than 25 alphanumeric characters as
requiring OCR. Processing is limited to 50 pages and 120,000 extracted
characters. This step does not run OCR, AI extraction, or database persistence.

## Invoice OCR and extraction

Uploads explicitly categorized as `invoice`, `receipt`, or `bill` are processed
in the background. PDF pages without enough digital text and supported JPG/PNG
images use PaddleOCR locally; extracted text is sent to Groq for structured
field extraction and validated before it is saved to
`documents.extracted_data`. The document status changes from `uploaded` to
`processing`, then to `processed` or `failed`. Other and missing document types
are not sent to OCR or Groq. Extracted fields are not automatically written to
service-record or expense tables unless business validation succeeds. A
successful integration creates one service record linked to the source document
with `source_type="invoice"` and one expense per priced line item in the same
database transaction. Manually entered records default to
`source_type="manual"`. Documents flagged for manual review keep their extracted
JSON but do not create normalized records. The extracted invoice date is kept
distinct from the service date; an invoice date alone is never treated as a
service date. Existing cost columns are floating-point and do not store
currency, so the original currency remains available only in the extracted
JSON.

Set `GROQ_API_KEY` in the private `backend/.env` for local runs, or in the
project-root `.env` when using Docker Compose. `GROQ_MODEL` and `OCR_LANG` can
be adjusted there; the defaults are `llama-3.3-70b-versatile` and `en`.
PaddleOCR downloads its recognition models on first use and runs inference
locally. Groq receives the extracted invoice text, so only upload documents
after considering that third-party data transfer. Do not put API keys in source
control.

## Service history schemas

`app.schemas.service_history` defines create, update, and response schemas for
service records. Request schemas reject client-supplied provenance fields; the
backend controls whether a record is `manual` or `invoice` sourced. Service
layer functions and authenticated service-history API routes are implemented.
Exact matching by vehicle, service date, odometer, and normalized service type
returns a conflict instead of creating a duplicate. Invoice matches become
manual-review warnings in the extraction JSON rather than being silently
discarded. Deleting a service record preserves related expenses and detaches
them from that record.

## Maintenance predictions

`GET /maintenance/vehicles/{vehicle_id}/predictions` returns a deterministic
maintenance forecast for the authenticated vehicle owner. Predictions use
active, effective maintenance rules that match the vehicle and its model year,
then compare the latest service record with the current odometer and date.
Status priority is overdue, unknown, due soon, then not due; missing history or
an odometer lower than the last recorded service produces an unknown status.
Responses include the rule's source title and URL. No manufacturer intervals
are preloaded: add only maintenance rules verified against reliable sources.
Apply the pending database migration with `alembic upgrade head` before using
the endpoint.

## Expense analytics

The authenticated expense analytics endpoints provide:

- `GET /analytics/vehicles/{vehicle_id}/summary`
- `GET /analytics/vehicles/{vehicle_id}/categories`
- `GET /analytics/vehicles/{vehicle_id}/monthly`
- `GET /analytics/vehicles/{vehicle_id}/yearly`
- `GET /analytics/vehicles/{vehicle_id}/services`
- `GET /analytics/expenses/comparison`

Vehicle-specific endpoints require ownership of the requested vehicle. Vehicle
comparison is limited to the authenticated user's vehicles. Analytics aggregate
the existing `Expense.amount` values; the current schema has no currency or
refund fields, so all amounts must be interpreted as a common currency and
refund behavior is not inferred.

## Internet-sourced maintenance assistant

`POST /assistant/vehicles/{vehicle_id}/ask` searches for vehicle-specific
maintenance information, indexes extracted source text in a persistent local
ChromaDB collection, retrieves and reranks matching passages, and generates an
answer with source citations. The route requires authentication and vehicle
ownership. Engine and market are optional request fields; the system does not
assume those values when they are not supplied. It does not require owner or
service manuals to be uploaded.

Search includes manufacturer-targeted queries where the manufacturer domain is
known, plus a general fallback query. Returned URLs are inspected rather than
trusted based on search operators. Source categories contribute to a combined
relevance/reliability score, and answers with missing or unknown source IDs are
replaced with a safe insufficient-evidence response. This classification is a
ranking aid, not proof that a page is accurate or applicable to the exact
vehicle; verify critical maintenance intervals against official documentation.

Configure `TAVILY_API_KEY` and `GROQ_API_KEY` in the private `.env` before
calling the endpoint. The embedding and reranker models are configured by
`EMBEDDING_MODEL` and `RERANKER_MODEL`; their model files are downloaded the
first time each model is used. ChromaDB data is stored in
`backend/storage/chroma/` locally and in the `chroma-data` Docker volume.

Search queries, vehicle details, and retrieved excerpts are sent to Tavily and
Groq as part of this feature. Use those external services only after considering
that data transfer. Retrieved webpage text is treated as untrusted evidence;
answers should state when applicable vehicle-specific evidence is insufficient.

## Persistent AI mechanic conversations

The authenticated troubleshooting endpoints reuse the internet-sourced assistant
and store conversation history per vehicle:

- `POST /mechanic/vehicles/{vehicle_id}/ask` starts a conversation or continues
  one when a `session_id` is supplied.
- `GET /mechanic/vehicles/{vehicle_id}/sessions` lists the current user's
  conversations for that vehicle.
- `GET /mechanic/sessions/{session_id}/messages` returns a conversation's
  persisted messages.

The assistant uses recent conversation context and vehicle details when
searching, returns the same source citations as the maintenance assistant, and
does not expose sessions belonging to another user. If a message indicates
brake or steering failure, a fuel leak, smoke, fire, severe overheating, or an
oil-pressure warning, the endpoint responds with conservative safety guidance
instead of calling the AI providers. This is general guidance, not a diagnosis;
urgent situations require roadside assistance or local emergency services.
The diagnostic tables are included in the Alembic migrations; run
`alembic upgrade head` before using these endpoints.

## AI maintenance reminder agent

Authenticated reminder endpoints let users create date- and/or mileage-based
reminders, update or cancel them, mark them complete, and view in-app
notifications:

- `POST /reminders/vehicles/{vehicle_id}` — create a reminder
- `GET /reminders/vehicles/{vehicle_id}` — list a vehicle's reminders
- `PATCH /reminders/{reminder_id}` — update reminder details
- `POST /reminders/{reminder_id}/complete` — complete and advance a recurring
  reminder using only the recurrence intervals the user configured
- `DELETE /reminders/{reminder_id}` — cancel an active reminder
- `GET /reminders/notifications` — list notifications (supports
  `unread_only=true` and a bounded `limit`)
- `PATCH /reminders/notifications/{notification_id}/read` — mark a notification
  as read

The Celery Beat scheduler checks active reminders daily at 08:00 Asia/Kolkata;
the worker creates deduplicated upcoming or overdue notifications. Mileage
warnings use the configurable `REMINDER_MILEAGE_THRESHOLD_KM` policy (default
500 km), not a manufacturer maintenance interval. Both new database tables are
created by Alembic; apply the migration with `alembic upgrade head`.

For local development, set `REDIS_URL=redis://localhost:6379/0` in
`backend/.env`, start Redis, then run the worker and scheduler from `backend`:

```powershell
docker run --rm -d --name vehicle-redis -p 6379:6379 redis:7-alpine
celery -A app.core.celery_app.celery_app worker --loglevel=info --pool=solo
celery -A app.core.celery_app.celery_app beat --loglevel=info
```

Docker Compose starts PostgreSQL, Redis, the API, worker, and Beat together.
The Beat schedule, Redis data, PostgreSQL data, and ChromaDB data use persistent
volumes.

## Run with Docker Compose

Copy the root `.env.example` to `.env`, set a local PostgreSQL password and a
random `SECRET_KEY`, and configure `TAVILY_API_KEY` and `GROQ_API_KEY` to use
the AI features. Then run from the project root:

```powershell
docker compose up --build
```

Compose starts PostgreSQL, Redis, the API, Celery worker, Celery Beat, and the
production React frontend at <http://localhost:8080>. The API remains at
<http://localhost:8000>. PostgreSQL, Redis, Beat scheduling state, and ChromaDB
use named volumes; uploaded documents are persisted in
`backend/uploads/`. The backend entrypoint repairs ownership of its named data
volumes and drops the application process to a non-root user. On Linux, set
`APP_UID` and `APP_GID` in the root `.env` to the host account that owns
`backend/uploads/` so the container can write uploaded files.

For production configuration, set `APP_ENV=production`, use a PostgreSQL
`DATABASE_URL`, and set `CORS_ORIGINS` to explicit HTTPS frontend origins.
Set `VITE_API_URL` to the browser-reachable API URL before building the frontend;
Vite embeds this value in the static assets.
Production startup rejects SQLite and wildcard, HTTP, or malformed CORS
origins. Terminate TLS at a trusted reverse proxy; the Compose ports themselves
do not configure TLS. Keep the root `.env` private and use deployment-specific
secrets rather than the example values.

GitHub Actions runs backend tests and dependency checks, frontend lint/build,
and Docker Compose configuration validation on pushes and pull requests. The
Compose configuration check does not start containers; live Docker, Redis, and
Celery operation must be verified separately in an environment with Docker
Engine available.
