.PHONY: help venv install-dev install-hooks test test-contracts test-orchestrator test-openapi test-runner-assets check-console test-e2e test-e2e-smoke test-e2e-generated allure-info allure-generate allure-open allure-summary test-e2e-generated-allure test-open-report test-e2e-open-report test-e2e-smoke-open-report test-e2e-generated-open-report

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
	@echo "  make test               Run orchestrator and runner contract tests"
	@echo "  make test-contracts     Run all non-E2E contract/integration tests"
	@echo "  make test-orchestrator  Run ai-orchestrator pytest integration tests"
	@echo "  make test-openapi       Run ai-orchestrator OpenAPI contract tests"
	@echo "  make test-runner-assets Run web-playwright-python asset contract tests"
	@echo "  make check-console      Run static syntax check for the web console script"
	@echo "  make asset-tool-help    Show asset CLI usage"
	@echo "  make test-e2e           Run browser-based end-to-end tests"
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

venv:
	python3 -m venv .venv

install-dev: venv
	$(VENV_PYTHON) -m pip install --upgrade pip
	$(VENV_PYTHON) -m pip install -r requirements-dev.txt

install-hooks: install-dev
	$(VENV_PYTHON) -m pre_commit install

test: test-contracts

test-contracts: test-orchestrator test-runner-assets

test-orchestrator:
	$(PYTEST) -m integration apps/ai-orchestrator/tests/integration

test-openapi:
	$(PYTEST) apps/ai-orchestrator/tests/integration/test_openapi_contract.py

test-runner-assets:
	PYTHONPATH=runners/web-playwright-python $(PYTEST) -m contract runners/web-playwright-python/tests/test_asset_contracts.py runners/web-playwright-python/tests/test_asset_toolkit.py

check-console:
	node --check apps/web-console/static/app.js

asset-tool-help:
	PYTHONPATH=runners/web-playwright-python $(VENV_PYTHON) runners/web-playwright-python/tools/asset_cli.py --help

test-e2e:
	$(CHECK_BASE_URL)
	PYTHONPATH=runners/web-playwright-python $(PYTEST) -m e2e runners/web-playwright-python/tests

test-e2e-smoke:
	$(CHECK_BASE_URL)
	PYTHONPATH=runners/web-playwright-python $(PYTEST) -m "e2e and smoke" runners/web-playwright-python/tests

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
	PYTHONPATH=runners/web-playwright-python $(PYTEST) -m "e2e and smoke" runners/web-playwright-python/tests --alluredir runners/web-playwright-python/allure-results
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
