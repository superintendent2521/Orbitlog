# Orbital Log

Orbital Log is a FastAPI + PostgreSQL logging platform built around 16-digit workspace identifiers. Client applications send string payloads (plus optional structured metadata) to a workspace, and backend teams retrieve, filter, and aggregate the logs with millisecond timestamps and HTTP-style status buckets (200/300/400/500).

## Highlights

- **PostgreSQL-first** storage using SQLAlchemy 2.0 with async sessions and JSON columns.
- **Strict workspace IDs** – every request validates a 16-digit numeric identifier before it can be logged or queried.
- **Status-code tracking** – ingest, filter, and aggregate on the canonical 200/300/400/500 buckets to spot regressions quickly.
- **Async FastAPI app** with auto-created schema on startup, CORS enabled, and typed request/response models.
- **Benchmarks included** via `scripts/benchmark.py`, capable of hitting a running server or the app in-process.

## Project layout

```
app/
  config.py         # Settings + validation
  database.py       # Async engine/session + lifecycle helpers
  main.py           # FastAPI application & routers
  models.py         # SQLAlchemy ORM models
  schemas.py        # Pydantic request/response models
  utils.py          # Workspace validation helpers
scripts/
  benchmark.py      # Async load generator & reporter
```

## Quick start

1. **Install dependencies** (Python 3.10+)

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Start PostgreSQL** (local or container). A minimal Docker setup is included:

   ```powershell
   docker compose up -d db
   ```

3. **Configure the API**. Copy `.env.example` to `.env` and adjust credentials if needed. Default is `postgresql+asyncpg://orbital:orbital@localhost:5432/orbitallog`.

4. **Create the database once** (if it does not yet exist):

   ```powershell
   python -m scripts.create_database --dsn postgresql+asyncpg://postgres:<password>@localhost:5432/orbitallog
   ```

5. **Run the server**:

   ```powershell
   uvicorn app.main:app --reload
   ```

   Automatic migrations: the ORM schema is created on startup; no Alembic step is required for the first run.

6. **Interact with the API** via [http://localhost:8000/docs](http://localhost:8000/docs) or `curl`:

   ```bash
   curl -X POST http://localhost:8000/workspaces/1234567890123456/logs \
        -H "Content-Type: application/json" \
        -d '{
              "message": "Cache primed",
              "code": 200,
              "meta": {"host": "api-1"}
            }'

   curl "http://localhost:8000/workspaces/1234567890123456/logs?limit=20&code=400"
   curl http://localhost:8000/workspaces/1234567890123456/stats
   curl http://localhost:8000/stats/codes
   ```

## Docker

The included `docker-compose.yml` builds the API image and wires it to PostgreSQL:

```powershell
docker compose up --build
```

The API will be available on `http://localhost:8000` and points to the in-cluster Postgres by default.

## Benchmarking

`scripts/benchmark.py` fires concurrent ingest requests and prints latency/throughput metrics. It can either hit a running deployment or run the ASGI app in-process (using SQLite for convenience):

```powershell
# In-process benchmark (SQLite) used for the sample numbers below
python -m scripts.benchmark --inprocess --requests 500 --concurrency 50 --message-size 180

# Against a live server + Postgres
python -m scripts.benchmark --url http://localhost:8000 --workspace 5555555555555555 --requests 1000 --concurrency 80

# Multi-threaded HTTP run (total concurrency = threads * --concurrency)
python -m scripts.benchmark --url http://localhost:8000 --requests 2000 --concurrency 40 --threads 4
```

Sample output from the in-process run on this machine:

```
Benchmark Results
-----------------
duration     : 6.26 s
throughput   : 79.8 req/s
mean_latency : 0.58 s
p95_latency  : 1.35 s
p99_latency  : 4.38 s
successes    : 500
```

Use the provided options (`--requests`, `--concurrency`, `--message-size`, `--workspace`) to mirror real workloads. Use `--threads` to fan out across CPU cores when targeting remote servers; each thread runs its own set of `--concurrency` async workers so the effective concurrency is `threads * --concurrency`. The flag is ignored in `--inprocess` mode where the ASGI app is hosted inside the process already. For production-like numbers you should point the script at a deployed API backed by PostgreSQL.

## Environment variables

| Variable        | Default                                                         | Description                                  |
|-----------------|-----------------------------------------------------------------|----------------------------------------------|
| `DATABASE_URL`  | `postgresql+asyncpg://orbital:orbital@localhost:5432/orbitallog` | SQLAlchemy async connection string           |
| `ENVIRONMENT`   | `dev`                                                            | Arbitrary environment tag for logging        |

## API summary

| Endpoint | Description |
|----------|-------------|
| `POST /workspaces/{workspace_id}/logs` | Validate workspace ID and persist a log message with code + optional metadata |
| `GET /workspaces/{workspace_id}/logs` | Paginated retrieval with filters for code, text search, and time range |
| `GET /workspaces/{workspace_id}/stats` | Returns counts per 200/300/400/500 bucket plus totals for the workspace |
| `GET /stats/codes` | Global aggregation over all workspaces and distinct workspace count |
| `GET /healthz` | Simple health probe |

## Next steps

- Wire the ingestion endpoint behind auth (API keys, OAuth, or tenancy headers).
- Extend status tracking to arbitrary tags (region, version, etc.) and expose more analytics endpoints.
- Ship the benchmark results to dashboards or CI to catch regressions automatically.