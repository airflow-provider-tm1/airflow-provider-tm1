from datetime import timedelta

from airflow import DAG
from airflow.utils.dates import days_ago

from airflow_provider_tm1.operators.tm1_run_ti import TM1RunTIOperator

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
        'airflow_test_dry_run_dag',
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
        timeout=300,
        tm1_dry_run=True
    )

    t1
