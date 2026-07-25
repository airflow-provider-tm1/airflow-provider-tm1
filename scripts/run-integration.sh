#!/usr/bin/env bash
#
# run-integration.sh -- run the TM1 integration test suite locally.
#
# Replicates the CI flow on this machine (which is on the tailnet, with the
# airflow + TM1 images cached locally -- so pulls/builds that take CI minutes
# or time out entirely happen in seconds here):
#
#   build wheel -> write tests_integration/.env -> compose up airflow-init
#   -> compose up --build -> add tm1_conn -> pytest -> teardown
#
# Designed to run as a pre-push hook (see .githooks/pre-push) or manually via
# `make integration`. Brings the stack up fresh and tears it down afterwards;
# the postgres volume is kept (no -v) so airflow-init's DB migration is faster
# next time.
#
# Usage:
#   scripts/run-integration.sh                 # Airflow 2.11 (default)
#   AIRFLOW_BASE_IMAGE=apache/airflow:3.0.6-python3.11 scripts/run-integration.sh
#   SKIP_DOWN=1 scripts/run-integration.sh     # leave the stack running on success
#
set -euo pipefail

# --- paths -------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
INTEG_DIR="$REPO_ROOT/tests_integration"

# --- config ------------------------------------------------------------------
AIRFLOW_BASE_IMAGE="${AIRFLOW_BASE_IMAGE:-apache/airflow:2.11.0-python3.11}"
WORKER_CONTAINER="tests_integration-airflow-worker-1"

cd "$REPO_ROOT"

# --- prereq checks (fail fast with a useful message) -------------------------
echo "==> Checking prerequisites ..."
command -v docker >/dev/null 2>&1 || { echo "::error::docker not found in PATH"; exit 1; }
docker info >/dev/null 2>&1 || { echo "::error::docker daemon not reachable"; exit 1; }

if ! docker image inspect "$AIRFLOW_BASE_IMAGE" >/dev/null 2>&1; then
  echo "::error::base image $AIRFLOW_BASE_IMAGE not cached locally."
  echo "   Pull it first:  docker pull $AIRFLOW_BASE_IMAGE"
  exit 1
fi

if ! docker image inspect 100.109.186.25:5100/tm1-linux:24Retail >/dev/null 2>&1; then
  echo "::error::TM1 image not cached locally and this machine may not be on the tailnet."
  echo "   The integration suite requires the TM1 container; CI can't run it within timeout."
  exit 1
fi

# --- build the wheel (the provider has to be importable inside the image) ----
echo "==> Building wheel ..."
python3 -m pip install --upgrade pip build --quiet
python3 -m build >/dev/null

# --- compose .env ------------------------------------------------------------
echo "==> Writing tests_integration/.env (AIRFLOW_BASE_IMAGE=$AIRFLOW_BASE_IMAGE) ..."
{
  echo "AIRFLOW_UID=$(id -u)"
  echo "AIRFLOW_BASE_IMAGE=${AIRFLOW_BASE_IMAGE}"
} > "$INTEG_DIR/.env"

# --- bring up the stack ------------------------------------------------------
# teardown on any exit (success, failure, Ctrl-C) unless SKIP_DOWN is set.
cleanup() {
  if [ "${SKIP_DOWN:-0}" = "1" ]; then
    echo "==> SKIP_DOWN=1: leaving stack running."
    return
  fi
  echo "==> Tearing down stack (docker compose down) ..."
  (cd "$INTEG_DIR" && docker compose down) || true
}
trap cleanup EXIT

echo "==> airflow-init (DB migration + admin user) -- first run builds the image ..."
(cd "$INTEG_DIR" && docker compose up -d airflow-init)

echo "==> Starting full stack ..."
(cd "$INTEG_DIR" && docker compose up -d --build)

# Wait for the TM1 container to be healthy before running tests. No airflow
# service depends on TM1, so without this pytest fires before TM1 has finished
# booting. TM1's cold boot of the full 24Retail model can take several minutes,
# so the cap matches compose's own healthcheck tolerance (10 retries * 2m).
echo "==> Waiting for TM1 to become healthy (cold boot of 24Retail can take several minutes) ..."
TM1_CONTAINER="tm1"
deadline=$(( $(date +%s) + 900 ))   # 15 min cap (matches the CI job timeout)
while :; do
  status="$(docker inspect --format '{{.State.Health.Status}}' "$TM1_CONTAINER" 2>/dev/null || echo "missing")"
  case "$status" in
    healthy) echo "    TM1 is healthy."; break ;;
    unhealthy) echo "::error::TM1 container is unhealthy. Check: docker logs $TM1_CONTAINER"; exit 1 ;;
    missing) echo "::error::TM1 container $TM1_CONTAINER not found."; exit 1 ;;
  esac
  if [ "$(date +%s)" -ge "$deadline" ]; then
    echo "::error::Timed out waiting for TM1 health (last status: $status)."
    echo "          Check: docker logs $TM1_CONTAINER"
    exit 1
  fi
  printf '.';
  sleep 5
done
echo

# --- add the TM1 connection if not present -----------------------------------
echo "==> Ensuring tm1_conn exists in Airflow ..."
if DOCKID=$(docker ps -q --filter "name=$WORKER_CONTAINER") && [ -n "$DOCKID" ]; then
  if ! docker exec "$DOCKID" airflow connections list 2>/dev/null | grep -q tm1_conn; then
    docker exec "$DOCKID" airflow connections add 'tm1_conn' \
      --conn-json '{"conn_type": "tm1", "host": "tm1", "login": "admin", "schema": "", "port": 5360, "extra": {"ssl": "False"}}'
    echo "    added tm1_conn"
  else
    echo "    tm1_conn already present"
  fi
else
  echo "::error::$WORKER_CONTAINER not running; aborting."
  exit 1
fi

# --- run the tests -----------------------------------------------------------
echo "==> Running pytest ..."
python3 -m pytest "$INTEG_DIR/integration_test.py" -s

echo "==> Integration tests passed."
