# Base Airflow image is parameterized via build-arg so the same Dockerfile
# can build against either Airflow 2.11 or 3.x (see docker-compose.yaml / CI matrix).
ARG AIRFLOW_BASE_IMAGE=apache/airflow:2.11.0-python3.11
FROM ${AIRFLOW_BASE_IMAGE}

# Speed up pip and silence version noise; keep it deterministic for layer caching.
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

# The base image ships a pip wrapper that REFUSES to run as root, and the
# 'airflow' user already owns its Python environment + /opt/airflow. So we stay
# on the default 'airflow' user for every pip/mkdir step. Do NOT switch to root.
USER airflow

# The base image ALREADY contains apache-airflow. The provider only needs these
# additional runtime deps; installing just them avoids re-resolving (and
# potentially re-downloading) the entire Airflow dependency tree on every build.
RUN pip install pandas \
 && pip install TM1py>=2.1 \
 && pip install "apache-airflow-providers-common-compat>=1.16.0"

# 'python -m build' below needs the build frontend; not present in the base image.
RUN pip install build

# Copy build metadata first so source changes don't bust the deps layer above.
ADD --chown=airflow:root pyproject.toml setup.py requirements.txt README.md LICENSE /tmp/
ADD --chown=airflow:root airflow_provider_tm1 /tmp/airflow_provider_tm1

WORKDIR /tmp

# Build the wheel, then install it with --no-deps: the base image already has
# Airflow and the two providers above cover the provider's other runtime deps,
# so we avoid triggering a full Airflow dependency resolution here.
RUN python -m build && \
    VERSION=$(grep '__version__ =' airflow_provider_tm1/__init__.py | awk -F '"' '{print $2}' | head -1) && \
    pip install --no-deps "dist/airflow_provider_tm1-$VERSION-py3-none-any.whl"

RUN mkdir -p /opt/airflow/csv
