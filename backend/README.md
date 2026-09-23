# AURELIS Intelligence API — backend (MODULE 2)

Deterministic local backend for the AURELIS assistant frontend. No external
model provider is called: responses are synthesised by a seeded simulator, so
the API is reproducible and safe to run offline.

## Stack

FastAPI · SQLAlchemy 2.0 · Alembic · Pydantic v2 · SQLite (PostgreSQL-ready)

## Setup

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # adjust if needed
alembic upgrade head          # create the schema
python -m app.db.seed         # load reference + demo data
```

## Run

```bash
python run.py                 # uvicorn with reload on 0.0.0.0:12001
```

Or without reload, which is what a deployed process should use:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 12001
```

## Verify

```bash
pytest                        # 90 tests
curl localhost:12001/api/v1/health/ready
```

## Docs

- Swagger UI: `http://localhost:12001/docs`
- OpenAPI JSON: `http://localhost:12001/openapi.json`

## Layout

| Path | Responsibility |
| --- | --- |
| `app/api/v1/` | HTTP routes, grouped by domain |
| `app/schemas/` | Pydantic wire models — the frontend contract |
| `app/models/` | SQLAlchemy tables |
| `app/services/` | Business logic, incl. the engine seam |
| `app/services/engine/` | `simulator` provider; MODULE 6 adds a real one |
| `app/db/` | Session handling and seed data |
| `alembic/` | Schema migrations |
| `tests/` | Contract, behaviour and migration tests |

## Notes for later modules

- **Wire format.** `src/types.ts` in the frontend is the source of truth.
  Timestamps the UI does arithmetic on are epoch milliseconds; the two fields
  the UI prints verbatim (`activity.at`, `knowledge.updated`, `memory.learned`)
  are pre-formatted relative strings. `tests/test_contract.py` locks this.
- **Provider seam.** `AI_PROVIDER=simulator` is the only implementation today.
  MODULE 6 registers a real provider without touching callers.
- **Migrations.** Add migrations rather than editing `0001`; that revision is
  only safe to amend while the schema is unreleased. `alembic revision
  --autogenerate` is checked for drift in `tests/test_migrations.py`.
