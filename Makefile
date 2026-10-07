PY ?= python
COMPOSE := docker compose --env-file .env -f infra/docker-compose.yml

.PHONY: install lint format-check audit smoke test test-unit test-integration test-scenarios eval build up down logs dashboard-dev index-runbooks
lint:
	$(PY) -m ruff check healer demo_services evals scripts

format-check:
	$(PY) -m ruff format --check healer demo_services evals scripts

audit:
	$(PY) scripts/audit_dependencies.py

smoke:
	$(PY) scripts/smoke_deployment.py

install:
	$(PY) -m pip install -r healer/requirements.txt

test:
	$(PY) -m pytest healer/tests -q

test-unit:
	$(PY) -m pytest healer/tests/unit -q

test-integration:
	$(PY) -m pytest healer/tests/integration -q

test-scenarios:
	$(PY) -m pytest healer/tests/scenarios -q

eval:
	$(PY) evals/run_evals.py

build:
	$(COMPOSE) build

up:
	$(COMPOSE) up -d

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f healer

dashboard-dev:
	npm --prefix dashboard ci
	npm --prefix dashboard run dev

index-runbooks:
	$(PY) scripts/index_runbooks.py --query "high memory usage"
