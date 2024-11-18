FROM apache/airflow:2.9.1

ADD airflow_provider_tm1 /tmp/airflow_provider_tm1
ADD pyproject.toml /tmp/pyproject.toml
ADD requirements.txt /tmp/requirements.txt
WORKDIR /tmp

RUN python -m pip install -r requirements.txt &&\
    python -m build
RUN VERSION=$(grep '__version__ =' airflow_provider_tm1/__init__.py | awk -F '"' '{print $2}') && \
    echo "Version is $VERSION" && \
    pip install "dist/airflow_provider_tm1-$VERSION-py3-none-any.whl"

