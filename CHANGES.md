# Changes in this update

All new code was tested with the unit suite (79 tests, 74 % line coverage of `app`).
Not run by the author of the changes: docker compose, the Kubernetes deployment and the GitHub Actions workflow.
You must run them and confirm the result before you write "deployed" or "tested" in a report.

## New files
- `backend/app/core/resilience.py` retry with backoff and jitter, circuit breaker
- `backend/app/core/metrics.py`, `metrics_middleware.py` Prometheus metrics (route template labels)
- `backend/workers/common.py` SIGTERM/SIGINT handling
- `backend/tests/test_resilience.py`, `test_ops_endpoints.py`, `test_outbox_mode.py`, `test_worker.py` (22 tests)
- `infrastructure/docker/Dockerfile` (was empty), `.dockerignore`, `.env.example`
- `docker-compose.yml` full stack (your old file is kept as `docker-compose.old.yml`)
- `infrastructure/monitoring/prometheus/prometheus.yml`, `alerts.yml` (11 rules), Grafana provisioning and `rtap-overview.json`
- `k8s/` 26 Kubernetes resources, `k8s/README.md`
- `.github/workflows/ci.yml`

## Changed files
- `app/main.py` lifespan instead of on_event, metrics middleware, `/metrics`, `/alive`, `/ready`
- `app/core/config.py` new settings (SQL_ECHO, INGEST_MODE, retry and breaker values, DLQ topic, metrics ports); the default database password was removed from the code
- `app/db/session.py` SQL echo now uses `SQL_ECHO`, not `DEBUG`
- `app/services/transaction_service.py` `INGEST_MODE=sync` (variant A) or `outbox` (variant B)
- `kafka/consumer.py` lag method
- `workers/outbox_publisher.py` retry, breaker, metrics, one UPDATE per published row, clean stop
- `workers/transaction_worker.py` retry, dead-letter topic, transient vs permanent errors, metrics, clean stop
- `tests/conftest.py` sync mode for the old tests, closes the SQLite thread so pytest exits

## Run
    cd backend && python -m pytest                 # 79 tests
    docker compose up --build                      # API :8000, Prometheus :9090, Grafana :3000 (admin/admin)
    INGEST_MODE=sync docker compose up -d api      # variant A (scoring inside the request)
    INGEST_MODE=outbox docker compose up -d api    # variant B

Create a user through /docs (register), then run your k6 scripts. For repeat measurements use:
SQL echo off (default), DATABASE_POOL_SIZE=20 (default), random customer ids, warm-up, p99 in k6 `summaryTrendStats`.

## Security
The old default `DATABASE_URL` in `config.py` contained a real password and was committed to GitHub.
Change that password. `.env` is ignored by git, do not put it into archives you share.

## Line endings
Edited files use LF. Add a `.gitattributes` with `* text=auto` if git shows whole files as changed.
