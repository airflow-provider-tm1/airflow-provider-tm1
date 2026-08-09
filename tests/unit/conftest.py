"""Test configuration for unit tests.

Unit tests run against mocked TM1 services (no docker stack). They import Airflow
only through the provider's hook, so they need a writable AIRFLOW_HOME to avoid
Airflow's logging-config side effect at import time.
"""

import os
import tempfile
from pathlib import Path

# Airflow's import-time logging config tries to mkdir $AIRFLOW_HOME/logs/... .
# Point it at a temp dir so importing the provider works in any environment
# (CI runners, fresh checkouts) without permission errors.
_AIRFLOW_HOME = Path(tempfile.gettempdir()) / "airflow-unit-tests"
(_AIRFLOW_HOME / "logs" / "scheduler").mkdir(parents=True, exist_ok=True)
os.environ.setdefault("AIRFLOW_HOME", str(_AIRFLOW_HOME))
os.environ.setdefault("AIRFLOW__CORE__DAGS_FOLDER", str(_AIRFLOW_HOME / "dags"))
os.environ.setdefault("AIRFLOW__LOGGING__LOGGING_LEVEL", "ERROR")
