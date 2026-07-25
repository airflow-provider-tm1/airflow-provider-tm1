.PHONY: integration integration-3.0 integration-down integration-logs help

# Default Airflow version for local integration runs. Override inline:
#   make integration AIRFLOW_BASE_IMAGE=apache/airflow:3.0.6-python3.11
AIRFLOW_BASE_IMAGE ?= apache/airflow:2.11.0-python3.11

help:
	@echo "Targets:"
	@echo "  integration       Run the TM1 integration suite locally (Airflow 2.11)"
	@echo "  integration-3.0   Same, against Airflow 3.0"
	@echo "  integration-down  Stop & remove the integration stack (keeps postgres volume)"
	@echo "  integration-logs  Tail the airflow-worker logs"
	@echo ""
	@echo "The suite also runs automatically on 'git push' (pre-push hook) when files"
	@echo "under airflow_provider_tm1/ or tests_integration/ have changed."

integration:
	AIRFLOW_BASE_IMAGE="$(AIRFLOW_BASE_IMAGE)" scripts/run-integration.sh

integration-3.0:
	$(MAKE) integration AIRFLOW_BASE_IMAGE=apache/airflow:3.0.6-python3.11

integration-down:
	cd tests_integration && docker compose down

integration-logs:
	docker logs -f tests_integration-airflow-worker-1
