SHELL := powershell.exe
.SHELLFLAGS := -NoProfile -Command

PY := .\healer\.venv\Scripts\python.exe
PIP := $(PY) -m pip
COMPOSE := docker compose -f infra\docker-compose.yml

.PHONY: install test test-unit test-integration test-scenarios eval build up down logs trigger-incident dashboard-dev index-runbooks

install:
	$(PIP) install -r healer\requirements.txt

test: test-unit

test-unit:
	$(PY) -m pytest healer\tests\unit -q

test-integration:
	$(PY) -m pytest healer\tests\integration -q

test-scenarios:
	$(PY) -m pytest healer\tests\scenarios -q

eval:
	$(PY) evals\run_evals.py

build:
	$(COMPOSE) build

up:
	$(COMPOSE) up -d

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f healer

trigger-incident:
	if (-not "$(SERVICE)") { throw "Usage: make trigger-incident SERVICE=leaky_service" }; Invoke-RestMethod -Method Post -Uri http://localhost:8000/demo/incident -ContentType application/json -Body (@{ service = "$(SERVICE)" } | ConvertTo-Json)

dashboard-dev:
	cd dashboard; npm install; npm run dev

index-runbooks:
	$(PY) scripts\index_runbooks.py --query "high memory usage"
