# PRAMAAN Backend — README

## Quickstart (5 commands)

```bash
# 1. Clone and enter backend
cd "sih 26245/backend"

# 2. Install dependencies
pip install -e ".[dev]"

# 3. Copy environment file
cp .env.example .env

# 4. Start infrastructure + API
docker compose -f deploy/docker-compose.yml up -d

# 5. Run tests
pytest
```

The API will be available at `http://localhost:8000/v1/docs`.

## Architecture

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full system design.

## Phase Status

See [`STATUS.md`](STATUS.md) for current implementation status and known limitations.

## Key Endpoints (Phase 1)

| Endpoint | Description |
|----------|-------------|
| `GET /v1/healthz` | Liveness probe (always 200) |
| `GET /v1/readyz` | Readiness probe (checks Postgres, Redis, S3) |
| `GET /v1/docs` | Interactive API documentation (dev only) |

## Development

```bash
# Run linting
ruff check .

# Run type checking
mypy app/

# Run tests with coverage
pytest --cov=app --cov-report=html

# Generate Alembic migration (after model changes)
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head
```

## Configuration

All configuration is through environment variables. See `.env.example` for the full list.

Key variables:
- `DB_*` — PostgreSQL connection
- `REDIS_*` — Redis connection  
- `S3_*` — MinIO/S3 storage
- `AUTH_*` — JWT/OIDC settings
- `PRAMAAN_ENVIRONMENT` — `development|staging|production`

## Privacy

No faces, no names, no Aadhaar numbers, no biometrics are stored anywhere.
Attendance data is aggregate counts per batch-session only.
See [`docs/PRIVACY.md`](docs/PRIVACY.md) for the full data protection statement.
