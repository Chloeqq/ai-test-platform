.PHONY: help venv install-dev install-hooks frontend-install frontend-dev frontend-build db-bootstrap db-upgrade db-revision test test-contracts test-pipeline-contracts test-orchestrator test-openapi test-runner-assets test-webui-manifest-strict test-orchestrator-manifest-strict test-orchestrate-e2e-smoke check-console check-webui-static check-webui-pages static-baseline-fast static-baseline asset-tool-help test-e2e test-e2e-smoke test-e2e-generated test-e2e-login-demo test-e2e-login allure-info allure-generate allure-open allure-summary test-e2e-generated-allure test-open-report test-e2e-open-report test-e2e-smoke-open-report test-e2e-generated-open-report

VENV_PYTHON := .venv/bin/python
PYTEST := $(VENV_PYTHON) -m pytest
PYTEST_CONTRACT := $(PYTEST) -m "contract or integration"
BASE_URL ?= http://localhost:5173/login\#/login
CHECK_BASE_URL := $(VENV_PYTHON) runners/web-playwright-python/tools/check_base_url.py --base-url "$(BASE_URL)"

help:
	@echo "Available targets:"
	@echo "  make venv               Create the root Python virtualenv"
	@echo "  make install-dev        Install root development dependencies"
	@echo "  make install-hooks      Install git pre-commit hooks"
	@echo "  make frontend-install   Install TS+React frontend dependencies (web-ui-service/frontend)"
	@echo "  make frontend-dev       Run TS+React frontend dev server"
	@echo "  make frontend-build     Build TS+React frontend into app/static/react"
	@echo "  make db-bootstrap       Bootstrap web-ui-service DB into Alembic-managed state"
	@echo "  make db-upgrade         Run Alembic migrations for web-ui-service"
	@echo "  make db-revision MSG=... Create a new Alembic revision for web-ui-service"
	@echo "  make test               Run orchestrator and runner contract tests"
	@echo "  make test-contracts     Run all non-E2E contract/integration tests"
	@echo "  make test-orchestrator  Run ai-orchestrator pytest integration tests"
	@echo "  make test-openapi       Run ai-orchestrator OpenAPI contract tests"
	@echo "  make test-runner-assets Run web-playwright-python asset contract tests"
	@echo "  make test-webui-manifest-strict Run web-ui strict manifest checks with compat scan disabled"
	@echo "  make test-orchestrator-manifest-strict Run orchestrator strict execution_record checks with compat scan disabled"
	@echo "  make test-orchestrate-e2e-smoke Run real execute=true orchestrate smoke chain against local login-demo"
	@echo "  make check-console      Run static syntax check for the web console script"
	@echo "  make check-webui-static Run static syntax checks for core web-ui-service scripts"
	@echo "  make check-webui-pages  Smoke-check core web-ui-service pages with Playwright (requires local service)"
	@echo "  make static-baseline-fast Run ruff + scoped mypy static baseline (no pytest)"
	@echo "  make static-baseline    Run ruff + scoped mypy + pytest stable baseline"
	@echo "  make asset-tool-help    Show asset CLI usage"
	@echo "  make test-e2e           Run browser-based end-to-end tests"
	@echo "  make test-e2e-login-demo Run login validation E2E against in-repo demo (no external app)"
	@echo "  make test-e2e-login     Run login validation E2E against LOGIN_E2E_BASE_URL (needs TEST_USERNAME/PASSWORD)"
	@echo "  make test-e2e-smoke     Run curated smoke browser tests"
	@echo "  make test-e2e-generated Run AI-generated browser tests"
	@echo "  make test-open-report   Run the recommended E2E smoke set and open Allure"
	@echo "  make test-e2e-open-report Run all E2E tests, generate Allure HTML, and open it"
	@echo "  make test-e2e-smoke-open-report Run smoke E2E tests, generate Allure HTML, and open it"
	@echo "  make test-e2e-generated-allure Run AI-generated browser tests with allure-results output"
	@echo "  make test-e2e-generated-open-report Run AI-generated browser tests, generate Allure HTML, and open it"
	@echo "  make allure-info        Show current Allure CLI and report directories"
	@echo "  make allure-generate    Generate an Allure HTML report from allure-results"
	@echo "  make allure-open        Open the generated Allure HTML report"
	@echo "  make allure-summary     Build report_summary.txt from artifacts analysis files"

# 一键启动本地开发环境（postgres + redis + orchestrator + web + seed 数据）
# 需要 .env 文件（参考 .env.example）和 Docker
dev:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d postgres redis
	@sleep 3
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d orchestrator
	@sleep 2
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d web
	@sleep 3
	@echo "Bootstrapping seed data..."
	$(VENV_PYTHON) apps/web-ui-service/scripts/bootstrap_database.py
	$(VENV_PYTHON) -c "from app.core.database import engine, Base; import app.models.workbench_state; Base.metadata.create_all(bind=engine)"
	@echo ""
	@echo "============================================"
	@echo "  Dev ready:"
	@echo "  Web UI:      http://localhost:8013"
	@echo "  Orchestrator: http://localhost:8000"
	@echo "============================================"

dev-down:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml down

venv:
	python3 -m venv .venv

install-dev: venv
	$(VENV_PYTHON) -m pip install --upgrade pip
	$(VENV_PYTHON) -m pip install -r requirements-dev.txt -r apps/web-ui-service/requirements.txt -r apps/ai-orchestrator/requirements.txt -r runners/web-playwright-python/requirements.txt -r agents/test-design-agent/requirements.txt

install-hooks: install-dev
	$(VENV_PYTHON) -m pre_commit install

frontend-install:
	cd apps/web-ui-service/frontend && npm install --cache ../../../.npm-cache

frontend-dev:
	cd apps/web-ui-service/frontend && npm run dev

frontend-build:
	cd apps/web-ui-service/frontend && npm run build

db-bootstrap:
	cd apps/web-ui-service && ../../.venv/bin/python scripts/bootstrap_database.py
	# workbench_state 表由 create_all() 创建,不在 alembic 迁移中
	cd apps/web-ui-service && PYTHONPATH=.. ../../.venv/bin/python -c "from app.core.database import engine, Base; import app.models.workbench_state; Base.metadata.create_all(bind=engine)"

db-upgrade:
	cd apps/web-ui-service && ../../.venv/bin/alembic upgrade head
	# workbench_state 表不在 alembic 迁移中,补创建
	cd apps/web-ui-service && PYTHONPATH=.. ../../.venv/bin/python -c "from app.core.database import engine, Base; import app.models.workbench_state; Base.metadata.create_all(bind=engine)"

db-revision:
	cd apps/web-ui-service && ../../.venv/bin/alembic revision -m "$(MSG)"

test: test-unit test-contracts

verify-core-chain:
	$(VENV_PYTHON) scripts/verify_core_chain.py

test-contracts: test-pipeline-contracts test-orchestrator test-runner-assets test-webui-manifest-strict test-orchestrator-manifest-strict

test-pipeline-contracts:
	$(PYTEST) shared_backend/tests/test_execution_compiler_contract.py shared_backend/tests/test_pipeline_contract.py shared_backend/tests/test_contract_validator.py -v

test-orchestrator:
	$(PYTEST) -m integration apps/ai-orchestrator/tests/integration

test-openapi:
	$(PYTEST) apps/ai-orchestrator/tests/integration/test_openapi_contract.py

test-runner-assets:
	PYTHONPATH=runners/web-playwright-python $(PYTEST) -m contract runners/web-playwright-python/tests/test_asset_contracts.py runners/web-playwright-python/tests/test_asset_toolkit.py

test-webui-manifest-strict:
	EVIDENCE_MANIFEST_COMPAT_SCAN_ENABLED=false $(VENV_PYTHON) -c "import sys; sys.path.insert(0, 'apps/web-ui-service'); from app.core.config import get_settings; assert get_settings().evidence_manifest_compat_scan_enabled is False"
	EVIDENCE_MANIFEST_COMPAT_SCAN_ENABLED=false $(PYTEST) apps/web-ui-service/tests/integration/test_workbench_multisource_endpoints.py -k strict_mode

test-orchestrator-manifest-strict:
	EXECUTION_RECORD_COMPAT_BUILDER_ENABLED=false $(VENV_PYTHON) -c "import sys; sys.path.insert(0, 'apps/ai-orchestrator/src'); from orchestrator_service import OrchestratorService; assert OrchestratorService().execution_record_compat_builder_enabled is False"
	EXECUTION_RECORD_COMPAT_BUILDER_ENABLED=false $(PYTEST) apps/ai-orchestrator/tests/integration/test_orchestrator_service_asset_flow.py -k strict_mode

test-orchestrate-e2e-smoke:
	TEST_DESIGN_MODE=deterministic $(PYTEST) apps/ai-orchestrator/tests/integration/test_orchestrate_execute_true_e2e_smoke.py -v

	scripts/qa/check-web-ui-static.sh

check-webui-pages:
	$(VENV_PYTHON) scripts/qa/check_web_ui_pages.py --base-url http://127.0.0.1:8013

# 分两批运行以隔离 test-ordering 冲突(facade/precheck 的 monkeypatch 与其他测试互相污染)
test-unit:
	$(VENV_PYTHON) -m pytest apps/web-ui-service/tests/unit/test_workbench_facade.py apps/web-ui-service/tests/unit/test_precheck_selected_intents_service.py -q
	$(VENV_PYTHON) -m pytest apps/web-ui-service/tests/unit/ apps/ai-orchestrator/tests/unit/ --ignore=apps/web-ui-service/tests/unit/test_workbench_facade.py --ignore=apps/web-ui-service/tests/unit/test_precheck_selected_intents_service.py -q

static-baseline-fast:
	scripts/qa/run-static-baseline-fast.sh

static-baseline:
	scripts/qa/run-static-baseline.sh

asset-tool-help:
	PYTHONPATH=runners/web-playwright-python $(VENV_PYTHON) runners/web-playwright-python/tools/asset_cli.py --help

test-e2e:
	$(CHECK_BASE_URL)
	PYTHONPATH=runners/web-playwright-python $(PYTEST) -m e2e runners/web-playwright-python/tests

test-e2e-login-demo:
	$(VENV_PYTHON) runners/web-playwright-python/tools/run_login_e2e_demo.py

test-e2e-login:
	@test -n "$(TEST_USERNAME)" || (echo "Set TEST_USERNAME=... TEST_PASSWORD=... (optional: export LOGIN_E2E_BASE_URL for #/login style)"; exit 1)
	@test -n "$(TEST_PASSWORD)" || (echo "Set TEST_USERNAME=... TEST_PASSWORD=..."; exit 1)
	@login_url="$$LOGIN_E2E_BASE_URL"; \
		test -n "$$login_url" || login_url='http://localhost:5173/#/login'; \
		$(VENV_PYTHON) runners/web-playwright-python/tools/check_base_url.py --base-url "$$login_url"; \
		BASE_URL="$$login_url" TEST_USERNAME='$(TEST_USERNAME)' TEST_PASSWORD='$(TEST_PASSWORD)' \
		PYTHONPATH=runners/web-playwright-python:runners/web-playwright-python/tools \
		$(PYTEST) runners/web-playwright-python/tests/test_login_validation_e2e.py -m e2e -v

test-e2e-smoke:
	$(CHECK_BASE_URL)
	PYTHONPATH=runners/web-playwright-python $(PYTEST) -m "e2e and smoke" \
		runners/web-playwright-python/tests/test_project_manager_smoke.py \
		runners/web-playwright-python/tests/test_login_smoke.py \
		runners/web-playwright-python/tests/test_order_smoke.py \
		runners/web-playwright-python/tests/test_product_quick.py \
		runners/web-playwright-python/tests/test_product_smoke.py

test-e2e-generated:
	$(CHECK_BASE_URL)
	PYTHONPATH=runners/web-playwright-python $(PYTEST) -m "e2e and generated" runners/web-playwright-python/tests

test-e2e-generated-allure:
	$(CHECK_BASE_URL)
	PYTHONPATH=runners/web-playwright-python $(PYTEST) -m "e2e and generated" runners/web-playwright-python/tests --alluredir runners/web-playwright-python/allure-results

test-open-report: test-e2e-smoke-open-report

test-e2e-open-report:
	$(CHECK_BASE_URL)
	PYTHONPATH=runners/web-playwright-python $(PYTEST) -m e2e runners/web-playwright-python/tests --alluredir runners/web-playwright-python/allure-results
	$(MAKE) allure-generate
	$(MAKE) allure-open

test-e2e-smoke-open-report:
	$(CHECK_BASE_URL)
	PYTHONPATH=runners/web-playwright-python $(PYTEST) -m "e2e and smoke" \
		runners/web-playwright-python/tests/test_project_manager_smoke.py \
		runners/web-playwright-python/tests/test_login_smoke.py \
		runners/web-playwright-python/tests/test_order_smoke.py \
		runners/web-playwright-python/tests/test_product_quick.py \
		runners/web-playwright-python/tests/test_product_smoke.py \
		--alluredir runners/web-playwright-python/allure-results
	$(MAKE) allure-generate
	$(MAKE) allure-open

test-e2e-generated-open-report: test-e2e-generated-allure
	$(MAKE) allure-generate
	$(MAKE) allure-open

allure-info:
	$(VENV_PYTHON) runners/web-playwright-python/tools/manage_allure.py info

allure-generate:
	$(VENV_PYTHON) runners/web-playwright-python/tools/manage_allure.py generate

allure-open:
	$(VENV_PYTHON) runners/web-playwright-python/tools/manage_allure.py open

allure-summary:
	$(VENV_PYTHON) runners/web-playwright-python/tools/report_summary.py
