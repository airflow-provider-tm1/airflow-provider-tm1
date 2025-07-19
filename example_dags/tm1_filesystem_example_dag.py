"""
Example Airflow DAG demonstrating TM1 filesystem usage with ObjectStoragePath
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.io.path import ObjectStoragePath
from airflow.sdk import dag, task, ObjectStoragePath

# Default arguments for the DAG
default_args = {
    'owner': 'tm1-team',
    'depends_on_past': False,
    'start_date': datetime(2025, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retry_delay': timedelta(minutes=5),
}

@task(
    task_id='list_files',
)
def list_tm1_files(**context):
    """Task to list files in TM1"""
    
    tm1_dir = ObjectStoragePath("tm1://tm1_default@/",)
    
    files = list(tm1_dir.iterdir())
    print(f"✅ Found {len(files)} files in tm1://.")
    for file_path in files:
        print(f"   - {file_path}")
        
    return [file_path for file_path in files]
            

@task(
    task_id='write_tm1_file',
)
def write_tm1_file(**context):
    """Task to write a file to TM1"""
    
    # Write a sample file to TM1
    test_file = ObjectStoragePath("tm1://test_file.txt", conn_id="tm1_default")
    test_file.write_bytes(b"This is a sample output file written to TM1.")
    print("✅ Sample output file written to TM1")
    return test_file
        
@task(
    task_id='read_tm1_file',
)
def read_tm1_file(path: ObjectStoragePath, **context):
    """Task to read a file from TM1"""
    assert path.exists(), "File does not exist in TM1"  
    print(f"Reading file from TM1: {path}")
    content = path.read_bytes()
    print(f"✅ Read file from TM1: {len(content)} characters")

@dag(
    dag_id='tm1_filesystem_example',
    default_args=default_args,
    description='Example DAG using TM1 filesystem with ObjectStoragePath',
    catchup=False,
    tags=['tm1', 'filesystem', 'example'],
)
def tm1_filesystem_example_dag(): 
    """Example DAG demonstrating TM1 filesystem usage with ObjectStoragePath"""
    list_files_task = list_tm1_files()
    write_file_task = write_tm1_file()
    read_file_task = read_tm1_file(path=write_file_task)
    read_tm1_file.override(task_id='read_tm1_file_expanded').expand(path=list_files_task)


tm1_filesystem_example_dag()

