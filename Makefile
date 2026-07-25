.PHONY: setup integration integration-3.0 integration-down integration-logs lint help

# Default Airflow version for local integration runs. Override inline:
#   make integration AIRFLOW_BASE_IMAGE=apache/airflow:3.0.6-python3.11
AIRFLOW_BASE_IMAGE ?= apache/airflow:2.11.0-python3.11

help:
	@echo "Setup:"
	@echo "  make setup         uv sync + install pre-commit hooks (commit + pre-push)"
	@echo ""
	@echo "Development:"
	@echo "  make lint          Run pre-commit hooks (black, isort) on all files"
	@echo ""
	@echo "Integration (requires the tailnet + local TM1 image):"
	@echo "  integration        Run the TM1 integration suite locally (Airflow 2.11)"
	@echo "  integration-3.0    Same, against Airflow 3.0"
	@echo "  integration-down   Stop & remove the integration stack (keeps postgres volume)"
	@echo "  integration-logs   Tail the airflow-worker logs"
	@echo ""
	@echo "The integration suite also runs automatically on 'git push' (pre-commit"
	@echo "pre-push stage) when files under airflow_provider_tm1/ or tests_integration/"
	@echo "have changed. Bypass with: git push --no-verify"

# One-time setup: install deps + dev tools via uv, then install the git hooks.
setup:
	uv sync
	uv run pre-commit install
	uv run pre-commit install --hook-type pre-push

lint:
	uv run pre-commit run --all-files

integration:
	AIRFLOW_BASE_IMAGE="$(AIRFLOW_BASE_IMAGE)" scripts/run-integration.sh

integration-3.0:
	$(MAKE) integration AIRFLOW_BASE_IMAGE=apache/airflow:3.0.6-python3.11

integration-down:
	cd tests_integration && docker compose down

integration-logs:
	docker logs -f tests_integration-airflow-worker-1
