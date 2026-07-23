# Base Airflow image is parameterized via build-arg so the same Dockerfile
# can build against either Airflow 2.11 or 3.x (see docker-compose.yaml / CI matrix).
ARG AIRFLOW_BASE_IMAGE=apache/airflow:2.11.0-python3.11
FROM ${AIRFLOW_BASE_IMAGE}
RUN pip install pandas
RUN mkdir -p /opt/airflow/csv

ADD airflow_provider_tm1 /tmp/airflow_provider_tm1
ADD pyproject.toml /tmp/pyproject.toml
ADD setup.py /tmp/setup.py
ADD requirements.txt /tmp/requirements.txt
WORKDIR /tmp

USER root
RUN chmod u+x setup.py airflow_provider_tm1/__init__.py && \
    python -m pip install -r requirements.txt &&\
    python -m build
USER airflow
RUN VERSION=$(grep '__version__ =' airflow_provider_tm1/__init__.py | awk -F '"' '{print $2}' | head -1) && \
    pip install "dist/airflow_provider_tm1-$VERSION-py3-none-any.whl"