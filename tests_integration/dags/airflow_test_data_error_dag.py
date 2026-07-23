from datetime import datetime, timedelta

from airflow import DAG

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
        'airflow_test_data_error_dag',
        default_args=default_args,
        schedule=None,
        start_date=datetime(2025, 1, 1),
        tags=[],
        catchup=False,
        max_active_runs=1
) as dag:
    t1 = TM1RunTIOperator (
        task_id='t1',
        tm1_conn_id='tm1_conn',
        process_name='airflow_test_data_error',
        timeout=300
    )

    t1
