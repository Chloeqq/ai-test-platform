.PHONY: check-base-url test-e2e test-e2e-smoke test-e2e-generated test-e2e-allure test-e2e-smoke-allure test-e2e-generated-allure test-open-report test-e2e-open-report test-e2e-smoke-open-report test-e2e-generated-open-report allure-generate allure-open

VENV_PYTHON := ../../.venv/bin/python
PYTEST := $(VENV_PYTHON) -m pytest
BASE_URL ?= http://localhost:5173/login\#/login

check-base-url:
	$(VENV_PYTHON) tools/check_base_url.py --base-url "$(BASE_URL)"

test-e2e: check-base-url
	BASE_URL='$(BASE_URL)' PYTHONPATH=. $(PYTEST) -m e2e tests

test-e2e-smoke: check-base-url
	BASE_URL='$(BASE_URL)' PYTHONPATH=. $(PYTEST) -m "e2e and smoke" tests

test-e2e-generated: check-base-url
	BASE_URL='$(BASE_URL)' PYTHONPATH=. $(PYTEST) -m "e2e and generated" tests

test-e2e-allure: check-base-url
	BASE_URL='$(BASE_URL)' PYTHONPATH=. $(PYTEST) -m e2e tests --alluredir allure-results

test-e2e-smoke-allure: check-base-url
	BASE_URL='$(BASE_URL)' PYTHONPATH=. $(PYTEST) -m "e2e and smoke" tests --alluredir allure-results

test-e2e-generated-allure: check-base-url
	BASE_URL='$(BASE_URL)' PYTHONPATH=. $(PYTEST) -m "e2e and generated" tests --alluredir allure-results

test-open-report: test-e2e-smoke-open-report

allure-generate:
	$(VENV_PYTHON) tools/manage_allure.py generate

allure-open:
	$(VENV_PYTHON) tools/manage_allure.py open

test-e2e-open-report: test-e2e-allure
	$(MAKE) allure-generate
	$(MAKE) allure-open

test-e2e-smoke-open-report: test-e2e-smoke-allure
	$(MAKE) allure-generate
	$(MAKE) allure-open

test-e2e-generated-open-report: test-e2e-generated-allure
	$(MAKE) allure-generate
	$(MAKE) allure-open
