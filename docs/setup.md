# Setup

Follow the root README for the authenticated Docker stack. Ports are local-only:

| Service | Local port |
| --- | --- |
| Dashboard | 3000 |
| Healer API and `/docs` | 8000 |
| Prometheus | 9090 |
| Alertmanager | 9093 |
| Grafana | 3001 |
| PostgreSQL | 5432 |
| Loki | 3100 |

Grafana's username is `admin`; its generated password is in
`.secrets/grafana_password`. The dashboard key is `.secrets/healer_api_key`.
Never paste either key into an issue or commit.

If another app occupies a port, set `DASHBOARD_PORT`, `HEALER_PORT`, `PROMETHEUS_PORT`,
`GRAFANA_PORT`, `POSTGRES_PORT`, `ALERTMANAGER_PORT`, `LOKI_PORT`, `LEAKY_PORT`, or
`FLAKY_PORT` in `.env`. Update `CORS_ALLOWED_ORIGINS` and `VITE_HEALER_API_URL` when
changing UI/API ports, then rebuild the dashboard. The smoke script reads port
overrides from the shell environment.

## API development without Compose

Create and activate a Python virtual environment, then install
`healer/requirements.txt`. Configure `.env` with `ENVIRONMENT=development`,
`AUDIT_BACKEND=sqlite`, and a local `SQLITE_PATH`. Set `HEALER_API_KEY` if you want
authentication. An empty key disables authentication in development only.

```sh
python -m uvicorn healer.src.main:app --reload --host 127.0.0.1 --port 8000
```

Run `npm ci` and `npm run dev` from `dashboard/`. Without live monitoring, the API
reports unavailable telemetry. It never invents logs or deployment history.
To index Markdown runbooks, run `python scripts/index_runbooks.py` from the root.

## Tests

```sh
python -m pytest healer/tests -q
python evals/run_evals.py
```

Tests isolate credentials and use temporary SQLite files. The scenario suite uses
mocked external integrations. Evaluations have a fixed policy independent of `.env`.
Neither suite establishes live production readiness.
