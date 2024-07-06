import os
import shutil
from datetime import timedelta
from pathlib import Path

from airflow import DAG
from airflow.example_dags.example_task_group_decorator import task_2
from airflow.models import Variable
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator, BranchPythonOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from airflow.utils.dates import days_ago
from datetime import datetime

from airflow.utils.task_group import TaskGroup

from airflow_providers_tm1.operators.tm1_run_ti import TM1RunTIOperator

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email': ['airflow@example.com'],
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 0,
    'retry_delay': timedelta(minutes=5)
}


with DAG(
        'airflow_test_success_dag',
        default_args=default_args,
        schedule_interval=None,
        start_date=days_ago(1),
        tags=[],
        catchup=False,
        max_active_runs=1
) as dag:
    t1 = TM1RunTIOperator (
        task_id='t1',
        tm1_conn_id='tm1_conn',
        process_name='airflow_test_success',
        timeout=300
    )

    t1
