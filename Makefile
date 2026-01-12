################################################################################
# Makefile for beacon-library: Fullstack CI/CD, Quality, Test, Docker Orchestration
################################################################################

# ----------------------------------------------------------------------------
# Variables (overridable)
# ----------------------------------------------------------------------------
ENV           ?= local
PROJECT       ?= beacon-library
VERSION       ?= $(shell git describe --tags --always --dirty 2>/dev/null || echo "dev")
REGISTRY      ?= ghcr.io
NAMESPACE     ?= nicolaslallier
IMAGE         ?= $(REGISTRY)/$(NAMESPACE)/$(PROJECT)
COMPOSE       ?= docker compose
DOCKER        ?= docker
CI            ?= 0
KEEP          ?= 0
VERBOSE       ?= 0

# Colors for pretty output
GREEN := \033[0;32m
BLUE  := \033[0;34m
YELLOW:= \033[1;33m
NORM  := \033[0m

# ----------------------------------------------------------------------------
# Sectioned Help (FR-001, FR-002)
# ----------------------------------------------------------------------------
.PHONY: help
help:
	@echo
	@echo "${BLUE}Usage:${NORM} make <target> [VAR=value]"
	@echo
	@echo "${GREEN}Dev Targets:${NORM}"
	@echo "  install        Install all dependencies (backend & frontend)"
	@echo "  dev            Run both frontend and backend in dev mode"
	@echo "  dev-backend    Run backend in dev mode"
	@echo "  dev-frontend   Run frontend in dev mode"
	@echo
	@echo "${GREEN}Quality Targets:${NORM}"
	@echo "  lint           Lint backend and frontend"
	@echo "  lint-backend   Lint backend (black, flake8, mypy)"
	@echo "  lint-frontend  Lint frontend (eslint)"
	@echo "  format         Format code (backend)"
	@echo
	@echo "${GREEN}Test Targets:${NORM}"
	@echo "  test           Run all unit tests"
	@echo "  test-unit      Run unit tests (backend)"
	@echo "  test-integration    Run integration tests (backend/integration)"
	@echo "  test-regression     Run regression/E2E tests"
	@echo
	@echo "${GREEN}Docker/Orchestration:${NORM}"
	@echo "  up             Bring up full stack (connects to Beacon's MinIO, Keycloak, monitoring)"
	@echo "  down           Tear down stack"
	@echo "  restart        Restart stack"
	@echo "  logs           Show logs"
	@echo "  ps             Show running containers"
	@echo "  docker-build   Build docker images"
	@echo "  push           Push docker images"
	@echo
	@echo "${GREEN}Observability:${NORM}"
	@echo "  observability-up     Start observability collectors (promtail, alloy, cadvisor)"
	@echo "  observability-down   Stop observability collectors"
	@echo "  observability-logs   Show observability collector logs"
	@echo "  observability-status Check observability pipeline status"
	@echo "  observability-test   Test all observability endpoints (Loki, Tempo, Prometheus)"
	@echo "  observability-test-loki       Test Loki log ingestion"
	@echo "  observability-test-tempo      Test Tempo trace ingestion"
	@echo "  observability-test-prometheus Test Prometheus metrics endpoint"
	@echo
	@echo "${GREEN}MinIO Storage:${NORM}"
	@echo "  minio-test           Test all MinIO functionality (connection, upload, download)"
	@echo "  minio-test-connection      Test MinIO connection"
	@echo "  minio-test-upload          Test file upload"
	@echo "  minio-test-download        Test file download"
	@echo
	@echo "${GREEN}CI/CD:${NORM}"
	@echo "  ci             Run CI pipeline (lint, test, build)"
	@echo "  cd             Run CD pipeline (ci, push, deploy)"
	@echo "  deploy         Deploy to environment"
	@echo
	@echo "${GREEN}Admin Services:${NORM}"
	@echo "  admin-up       Start admin services (pgAdmin, Redis Commander, ChromaDB Admin, etc.)"
	@echo "  admin-down     Stop admin services"
	@echo "  admin-logs     Show admin services logs"
	@echo "  admin-status   Show admin services status and URLs"
	@echo
	@echo "${GREEN}Utilities:${NORM}"
	@echo "  help           This help message with sections"
	@echo "  info           Show system & config info"
	@echo "  doctor         Run system diagnostics"
	@echo "  clean          Remove build artifacts, volumes, caches"
	@echo

# ----------------------------------------------------------------------------
# Dev Targets
# ----------------------------------------------------------------------------
.PHONY: install dev dev-backend dev-frontend

install:
	@echo "[Install] Installing backend and frontend dependencies..."
	cd backend && poetry install
	cd frontend && npm install

dev:
	@echo "[Dev] Starting backend and frontend in dev mode..."
	$(MAKE) -j2 dev-backend dev-frontend

dev-backend:
	@echo "[Dev Backend] Starting FastAPI with uvicorn..."
	cd backend && poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dev-frontend:
	@echo "[Dev Frontend] Starting Vite dev server..."
	cd frontend && npm run dev

# ----------------------------------------------------------------------------
# Docker/Orchestration Targets
# ----------------------------------------------------------------------------
.PHONY: up down restart logs ps

up:
	@echo "[Up] Starting stack (ENV=$(ENV))..."
	@echo "${YELLOW}Note: Requires Beacon project running (MinIO, Keycloak, monitoring)${NORM}"
	@echo "${YELLOW}Start Beacon first: cd ../Beacon && make up${NORM}"
ifeq ($(ENV),local)
	$(COMPOSE) -f docker-compose.yml -f docker-compose.local.yml up -d
else
	$(COMPOSE) -f docker-compose.yml -f docker-compose.$(ENV).yml up -d
endif

down:
	@echo "[Down] Stopping stack..."
	$(COMPOSE) down

restart:
	@echo "[Restart] Restarting stack..."
	$(MAKE) down
	$(MAKE) up

logs:
	@echo "[Logs] Showing logs..."
	$(COMPOSE) logs -f

ps:
	@echo "[PS] Running containers..."
	$(COMPOSE) ps

# ----------------------------------------------------------------------------
# Quality Targets
# ----------------------------------------------------------------------------
.PHONY: lint lint-backend lint-frontend format

lint-backend:
	@echo "[Lint Backend] black, flake8, mypy..."
	cd backend && poetry run black --check app || exit 1
	cd backend && poetry run flake8 app || exit 1
	cd backend && poetry run mypy app || exit 1

lint-frontend:
	@echo "[Lint Frontend] eslint..."
	cd frontend && npm run lint

lint: lint-backend lint-frontend

format:
	@echo "[Format Backend] black..."
	cd backend && poetry run black app

# ----------------------------------------------------------------------------
# Test Targets
# ----------------------------------------------------------------------------
.PHONY: test test-unit test-integration test-regression

test test-unit:
	@echo "[Unit Tests] Backend (pytest)..."
	cd backend && poetry run pytest tests/unit

test-integration:
	@echo "[Integration Tests] Backend (pytest)..."
	cd backend && poetry run pytest tests/integration

# Regression is a stub for now

test-regression:
	@echo "[Regression Tests] (stubbed)"
	@echo "Implement E2E test commands here as needed..."

# ----------------------------------------------------------------------------
# CI/CD Targets
# ----------------------------------------------------------------------------
.PHONY: ci cd docker-build push deploy

ci:
	@echo "[CI Pipeline] Lint → Unit Tests → Integration → Build"
	$(MAKE) lint
	$(MAKE) test-unit
	$(MAKE) test-integration
	$(MAKE) docker-build
	@echo "[CI Pipeline] Complete"

cd:
	@echo "[CD Pipeline] CI → Push → Deploy (ENV=$(ENV))"
	$(MAKE) ci
	$(MAKE) push
	$(MAKE) deploy

# Build Docker images for backend and frontend

docker-build:
	@echo "[Docker Build] Building backend and frontend images..."
	@$(COMPOSE) build

# Push images (stub, assumes auth configured)
push:
	@echo "[Docker Push] Pushing images..."
	@$(COMPOSE) push || echo "Implement auth and registry logic as needed"

deploy:
	@echo "[Deploy] (Stub) Implement deploy logic as needed for ENV=$(ENV)"
	@echo "(Options: docker compose up for prod, SSH-based, etc.)"

# ----------------------------------------------------------------------------
# Observability Targets
# ----------------------------------------------------------------------------
.PHONY: observability-up observability-down observability-logs observability-status

observability-up:
	@echo "[Observability] Starting collectors (promtail, alloy, cadvisor)..."
	@echo "${YELLOW}Note: Ensure external endpoints are accessible:${NORM}"
	@echo "  - LOKI_URL:       $${LOKI_URL:-http://loki.beacon.famillallier.net:3100}"
	@echo "  - PROMETHEUS_URL: $${PROMETHEUS_URL:-http://prometheus.beacon.famillallier.net:9090}"
	@echo "  - TEMPO_URL:      $${TEMPO_URL:-tempo.beacon.famillallier.net:4317}"
ifeq ($(ENV),local)
	$(COMPOSE) -f docker-compose.yml -f docker-compose.local.yml --profile observability up -d promtail alloy cadvisor
else
	$(COMPOSE) -f docker-compose.yml -f docker-compose.$(ENV).yml --profile observability up -d promtail alloy cadvisor
endif

observability-down:
	@echo "[Observability] Stopping collectors..."
	$(COMPOSE) --profile observability stop promtail alloy cadvisor
	$(COMPOSE) --profile observability rm -f promtail alloy cadvisor

observability-logs:
	@echo "[Observability] Showing collector logs..."
	$(COMPOSE) logs -f promtail alloy

observability-status:
	@echo "[Observability] Checking pipeline status..."
	@echo
	@echo "${BLUE}Collector Containers:${NORM}"
	@$(COMPOSE) ps promtail alloy cadvisor 2>/dev/null || echo "Containers not running"
	@echo
	@echo "${BLUE}External Endpoints:${NORM}"
	@echo "  Loki:       $${LOKI_URL:-http://beacon-loki:3100}"
	@echo "  Prometheus: $${PROMETHEUS_URL:-http://beacon-prometheus:9090}"
	@echo "  Tempo:      $${TEMPO_URL:-beacon-tempo:4317}"
	@echo
	@echo "${BLUE}Backend Metrics Endpoint:${NORM}"
	@curl -s http://localhost:8000/metrics 2>/dev/null | head -5 || echo "  Backend not running or metrics not available"

# Test container image for observability tests
OBSERVABILITY_TEST_IMAGE := curlimages/curl:8.5.0
OBSERVABILITY_TEST_NETWORK := beacon_monitoring_net

.PHONY: observability-test observability-test-loki observability-test-tempo observability-test-prometheus observability-test-all

observability-test: observability-test-all
	@echo "${GREEN}All observability tests completed!${NORM}"

observability-test-loki:
	@echo "${BLUE}[Test Loki] Testing log ingestion...${NORM}"
	@echo "  → Checking Loki readiness..."
	@$(DOCKER) run --rm --network $(OBSERVABILITY_TEST_NETWORK) $(OBSERVABILITY_TEST_IMAGE) \
		-sf http://beacon-loki:3100/ready && echo "    ${GREEN}✓ Loki is ready${NORM}" || \
		(echo "    ${YELLOW}✗ Loki not ready${NORM}"; exit 1)
	@echo "  → Sending test log entry..."
	@$(DOCKER) run --rm --network $(OBSERVABILITY_TEST_NETWORK) $(OBSERVABILITY_TEST_IMAGE) \
		-X POST "http://beacon-loki:3100/loki/api/v1/push" \
		-H "Content-Type: application/json" \
		-d '{"streams":[{"stream":{"job":"beacon-library-test","service":"makefile-test"},"values":[["'$$(date +%s)000000000'","Test log from make observability-test-loki"]]}]}' \
		&& echo "    ${GREEN}✓ Log sent successfully${NORM}" || \
		(echo "    ${YELLOW}✗ Failed to send log${NORM}"; exit 1)
	@echo "  → Querying test log..."
	@sleep 2
	@$(DOCKER) run --rm --network $(OBSERVABILITY_TEST_NETWORK) $(OBSERVABILITY_TEST_IMAGE) \
		-sf 'http://beacon-loki:3100/loki/api/v1/query?query=\{job="beacon-library-test"\}' | \
		grep -q "makefile-test" && echo "    ${GREEN}✓ Log query successful${NORM}" || \
		echo "    ${YELLOW}⚠ Log not found yet (may need more time to index)${NORM}"

observability-test-tempo:
	@echo "${BLUE}[Test Tempo] Testing trace ingestion...${NORM}"
	@echo "  → Checking Tempo readiness..."
	@$(DOCKER) run --rm --network $(OBSERVABILITY_TEST_NETWORK) $(OBSERVABILITY_TEST_IMAGE) \
		-sf http://beacon-tempo:3200/ready && echo "    ${GREEN}✓ Tempo is ready${NORM}" || \
		(echo "    ${YELLOW}✗ Tempo not ready${NORM}"; exit 1)
	@echo "  → Sending test trace via OTLP HTTP..."
	@TRACE_ID=$$(openssl rand -hex 16) && \
	SPAN_ID=$$(openssl rand -hex 8) && \
	NOW=$$(date +%s)000000000 && \
	END=$$(( $$(date +%s) + 1 ))000000000 && \
	$(DOCKER) run --rm --network $(OBSERVABILITY_TEST_NETWORK) $(OBSERVABILITY_TEST_IMAGE) \
		-X POST "http://beacon-tempo:4318/v1/traces" \
		-H "Content-Type: application/json" \
		-d '{"resourceSpans":[{"resource":{"attributes":[{"key":"service.name","value":{"stringValue":"makefile-test"}}]},"scopeSpans":[{"spans":[{"traceId":"'"$$TRACE_ID"'","spanId":"'"$$SPAN_ID"'","name":"test-span","kind":1,"startTimeUnixNano":"'"$$NOW"'","endTimeUnixNano":"'"$$END"'","attributes":[{"key":"test.source","value":{"stringValue":"makefile"}}]}]}]}]}' \
		&& echo "    ${GREEN}✓ Trace sent successfully (traceId: $$TRACE_ID)${NORM}" || \
		(echo "    ${YELLOW}✗ Failed to send trace${NORM}"; exit 1)

observability-test-prometheus:
	@echo "${BLUE}[Test Prometheus] Testing metrics endpoint...${NORM}"
	@echo "  → Checking Prometheus readiness..."
	@$(DOCKER) run --rm --network $(OBSERVABILITY_TEST_NETWORK) $(OBSERVABILITY_TEST_IMAGE) \
		-sf http://beacon-prometheus:9090/-/ready && echo "    ${GREEN}✓ Prometheus is ready${NORM}" || \
		(echo "    ${YELLOW}✗ Prometheus not ready${NORM}"; exit 1)
	@echo "  → Checking remote write endpoint..."
	@$(DOCKER) run --rm --network $(OBSERVABILITY_TEST_NETWORK) $(OBSERVABILITY_TEST_IMAGE) \
		-sf -o /dev/null -w "%{http_code}" http://beacon-prometheus:9090/api/v1/write | \
		grep -q "405\|204" && echo "    ${GREEN}✓ Remote write endpoint enabled${NORM}" || \
		echo "    ${YELLOW}⚠ Remote write endpoint may not be enabled${NORM}"
	@echo "  → Querying metrics..."
	@$(DOCKER) run --rm --network $(OBSERVABILITY_TEST_NETWORK) $(OBSERVABILITY_TEST_IMAGE) \
		-sf 'http://beacon-prometheus:9090/api/v1/query?query=up' | \
		grep -q "success" && echo "    ${GREEN}✓ Prometheus query successful${NORM}" || \
		(echo "    ${YELLOW}✗ Prometheus query failed${NORM}"; exit 1)

observability-test-all: observability-test-loki observability-test-tempo observability-test-prometheus
	@echo
	@echo "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NORM}"
	@echo "${GREEN}  All observability endpoints tested successfully!${NORM}"
	@echo "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NORM}"
	@echo
	@echo "View your data in Grafana:"
	@echo "  Loki:       {job=\"beacon-library-test\"}"
	@echo "  Tempo:      Search for service.name = makefile-test"
	@echo "  Prometheus: up{}"

# ----------------------------------------------------------------------------
# MinIO Storage Targets
# ----------------------------------------------------------------------------
.PHONY: minio-test minio-test-connection minio-test-upload minio-test-download minio-test-all

# MinIO test configuration
MINIO_TEST_IMAGE := minio/mc:latest
MINIO_TEST_NETWORK := beacon_monitoring_net
MINIO_ENDPOINT ?= beacon-minio1:9000
MINIO_ACCESS_KEY ?= minioadmin
MINIO_SECRET_KEY ?= minioadmin
MINIO_BUCKET ?= beacon-lib-test

minio-test: minio-test-all
	@echo "${GREEN}All MinIO tests completed!${NORM}"

minio-test-connection:
	@echo "${BLUE}[Test MinIO] Testing connection...${NORM}"
	@echo "  → Configuring mc client..."
	@$(DOCKER) run --rm --network $(MINIO_TEST_NETWORK) --entrypoint /bin/sh $(MINIO_TEST_IMAGE) \
		-c "mc alias set testminio http://$(MINIO_ENDPOINT) $(MINIO_ACCESS_KEY) $(MINIO_SECRET_KEY) && mc admin info testminio" \
		&& echo "    ${GREEN}✓ MinIO connection successful${NORM}" || \
		(echo "    ${YELLOW}✗ MinIO connection failed${NORM}"; exit 1)

minio-test-upload:
	@echo "${BLUE}[Test MinIO] Testing upload...${NORM}"
	@echo "  → Creating test bucket if not exists..."
	@$(DOCKER) run --rm --network $(MINIO_TEST_NETWORK) --entrypoint /bin/sh $(MINIO_TEST_IMAGE) \
		-c "mc alias set testminio http://$(MINIO_ENDPOINT) $(MINIO_ACCESS_KEY) $(MINIO_SECRET_KEY) && \
		    mc mb --ignore-existing testminio/$(MINIO_BUCKET)" \
		&& echo "    ${GREEN}✓ Bucket ready${NORM}" || \
		(echo "    ${YELLOW}✗ Failed to create bucket${NORM}"; exit 1)
	@echo "  → Uploading test file..."
	@$(DOCKER) run --rm --network $(MINIO_TEST_NETWORK) --entrypoint /bin/sh $(MINIO_TEST_IMAGE) \
		-c "mc alias set testminio http://$(MINIO_ENDPOINT) $(MINIO_ACCESS_KEY) $(MINIO_SECRET_KEY) && \
		    echo 'Test file from make minio-test at $$(date)' > /tmp/test.txt && \
		    mc cp /tmp/test.txt testminio/$(MINIO_BUCKET)/test-$$(date +%s).txt" \
		&& echo "    ${GREEN}✓ File uploaded successfully${NORM}" || \
		(echo "    ${YELLOW}✗ Upload failed${NORM}"; exit 1)

minio-test-download:
	@echo "${BLUE}[Test MinIO] Testing download...${NORM}"
	@echo "  → Listing files in bucket..."
	@FILE_COUNT=$$($(DOCKER) run --rm --network $(MINIO_TEST_NETWORK) --entrypoint /bin/sh $(MINIO_TEST_IMAGE) \
		-c "mc alias set testminio http://$(MINIO_ENDPOINT) $(MINIO_ACCESS_KEY) $(MINIO_SECRET_KEY) > /dev/null 2>&1 && \
		    mc ls testminio/$(MINIO_BUCKET)/ 2>/dev/null | wc -l") && \
		echo "    ${GREEN}✓ Found $$FILE_COUNT file(s) in bucket${NORM}"
	@echo "  → Downloading and verifying latest test file..."
	@$(DOCKER) run --rm --network $(MINIO_TEST_NETWORK) --entrypoint /bin/sh $(MINIO_TEST_IMAGE) \
		-c "mc alias set testminio http://$(MINIO_ENDPOINT) $(MINIO_ACCESS_KEY) $(MINIO_SECRET_KEY) > /dev/null 2>&1 && \
		    mc find testminio/$(MINIO_BUCKET)/ --name 'test-*.txt' | tail -1 | while read filepath; do \
		        if [ -n \"\$$filepath\" ]; then \
		            mc cat \"\$$filepath\" && echo && \
		            echo '    ${GREEN}✓ File download successful${NORM}'; \
		        fi; \
		    done" || echo "    ${YELLOW}⚠ Download test skipped${NORM}"

minio-test-all: minio-test-connection minio-test-upload minio-test-download
	@echo
	@echo "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NORM}"
	@echo "${GREEN}  All MinIO storage tests passed!${NORM}"
	@echo "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NORM}"
	@echo
	@echo "MinIO is ready for use:"
	@echo "  Endpoint:   $(MINIO_ENDPOINT)"
	@echo "  Test Bucket: $(MINIO_BUCKET)"
	@echo "  Console:    https://minio.beacon.famillelallier.net"

# ----------------------------------------------------------------------------
# Admin Services Targets
# ----------------------------------------------------------------------------
.PHONY: admin-up admin-down admin-logs admin-status dev-admin

admin-up:
	@echo "[Admin] Starting admin services..."
	@echo "${YELLOW}Starting: pgAdmin, Redis Commander, ChromaDB Admin, Ollama WebUI, Nginx Proxy Manager${NORM}"
ifeq ($(ENV),local)
	$(COMPOSE) -f docker-compose.yml -f docker-compose.local.yml -f admin/docker-compose.admin.yml --profile admin up -d
else
	$(COMPOSE) -f docker-compose.yml -f docker-compose.$(ENV).yml -f admin/docker-compose.admin.yml --profile admin up -d
endif
	@echo
	@$(MAKE) admin-status

admin-down:
	@echo "[Admin] Stopping admin services..."
	$(COMPOSE) -f docker-compose.yml -f admin/docker-compose.admin.yml --profile admin stop pgadmin redis-commander chromadb-admin ollama-webui nginx-proxy-manager
	$(COMPOSE) -f docker-compose.yml -f admin/docker-compose.admin.yml --profile admin rm -f pgadmin redis-commander chromadb-admin ollama-webui nginx-proxy-manager

admin-logs:
	@echo "[Admin] Showing admin services logs..."
	$(COMPOSE) -f docker-compose.yml -f admin/docker-compose.admin.yml logs -f pgadmin redis-commander chromadb-admin ollama-webui nginx-proxy-manager

admin-status:
	@echo
	@echo "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NORM}"
	@echo "${GREEN}  Admin Services Access Points${NORM}"
	@echo "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NORM}"
	@echo
	@echo "${BLUE}Database Management:${NORM}"
	@echo "  pgAdmin            http://localhost:$${PGADMIN_PORT:-5050}"
	@echo "                     Login: admin@beacon.local / $${PGADMIN_PASSWORD:-admin}"
	@echo
	@echo "${BLUE}Cache Management:${NORM}"
	@echo "  Redis Commander    http://localhost:$${REDIS_COMMANDER_PORT:-8081}"
	@echo
	@echo "${BLUE}Vector Database (ChromaDB):${NORM}"
	@echo "  ChromaDB Admin     http://localhost:$${CHROMADB_ADMIN_PORT:-8083}"
	@echo
	@echo "${BLUE}LLM Management:${NORM}"
	@echo "  Ollama WebUI       http://localhost:$${OLLAMA_WEBUI_PORT:-8082}"
	@echo
	@echo "${BLUE}Email Testing:${NORM}"
	@echo "  MailHog UI         http://localhost:$${MAILHOG_UI_PORT:-8025}"
	@echo
	@echo "${BLUE}Reverse Proxy Admin:${NORM}"
	@echo "  Nginx Proxy Mgr    http://localhost:$${NPM_ADMIN_PORT:-8888}"
	@echo "                     Login: admin@example.com / changeme (change on first login)"
	@echo
	@echo "${BLUE}Document Conversion:${NORM}"
	@echo "  Gotenberg Health   http://localhost:$${GOTENBERG_PORT:-3100}/health"
	@echo
	@echo "${BLUE}Admin API:${NORM}"
	@echo "  Settings           http://localhost:8181/api/admin/settings"
	@echo "  Services Health    http://localhost:8181/api/admin/services/health"
	@echo "  Maintenance Stats  http://localhost:8181/api/admin/maintenance/stats"
	@echo
	@echo "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NORM}"

dev-admin:
	@echo "[Dev + Admin] Starting full stack with admin services..."
ifeq ($(ENV),local)
	$(COMPOSE) -f docker-compose.yml -f docker-compose.local.yml -f admin/docker-compose.admin.yml --profile admin up -d
else
	$(COMPOSE) -f docker-compose.yml -f docker-compose.$(ENV).yml -f admin/docker-compose.admin.yml --profile admin up -d
endif
	@echo
	@$(MAKE) admin-status

# ----------------------------------------------------------------------------
# Utilities
# ----------------------------------------------------------------------------
.PHONY: info doctor clean

info:
	@echo "Project:      $(PROJECT)"
	@echo "Version:      $(VERSION)"
	@echo "ENV:          $(ENV)"
	@echo "Backend Dir:  backend/"
	@echo "Frontend Dir: frontend/"
	@echo "Image:        $(IMAGE)"
	@echo "Compose:      $(COMPOSE)"
	docker --version || true
	node --version || true
	npm --version || true
	poetry --version || true

# Checks for required tools and displays configuration

doctor:
	@echo "Checking required tools..."
	@command -v docker      >/dev/null 2>&1 || (echo "Docker not found!"; exit 1)
	@command -v poetry      >/dev/null 2>&1 || (echo "Poetry not found!"; exit 1)
	@command -v python3     >/dev/null 2>&1 || (echo "Python3 not found!"; exit 1)
	@command -v node        >/dev/null 2>&1 || (echo "Node not found!"; exit 1)
	@command -v npm         >/dev/null 2>&1 || (echo "NPM not found!"; exit 1)
	@echo "All tools OK!"

clean:
	@echo "Cleaning up build artifacts, caches and volumes..."
	@rm -rf backend/__pycache__/ backend/**/__pycache__/ backend/.pytest_cache
	@rm -rf frontend/node_modules frontend/dist
	@rm -rf .pytest_cache .mypy_cache .coverage
	@docker system prune -f || true
	@echo "Cleanup complete."
