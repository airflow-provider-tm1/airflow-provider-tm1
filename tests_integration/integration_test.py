from datetime import datetime
import logging
import os
import re
import subprocess
import time
import pytest

container_name = 'tests_integration-airflow-worker-1'

@pytest.fixture(autouse=True)
def setup_before_test(request):
    print("=============================================")
    print("Executing ", request.node.name)
    print("=============================================")

def run_docker_exec(command):
    
    result = subprocess.run(
        ['docker', 'exec', container_name] + command.split(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    output = result.stdout.decode("utf-8")
    print(output)
    
    return result, output

def assert_tm1server_log_contains(expected_line):
    test_folder = os.path.dirname(os.path.realpath(__file__))
    file_path = test_folder + '/tm1models/24Retail/tm1server.log'

    found = False
    start_time = time.time()
    timeout = 1
    while not found:
        time.sleep(0.1)
        if time.time() - start_time > timeout:
            print("Timeout reached. Exiting the loop.")
            break

        with open(file_path, "r") as file:
            file_content = file.read()

        found = re.search(expected_line, file_content)
    assert found
    
def assert_airflow_dag_log_contains(string, output):
    assert string in output

def assert_airflow_dag_completed(result):
    assert(result.returncode == 0)

def assert_airflow_dag_failed(result):
    assert(result.returncode == 1)

def test_airflow_test_success_dag():
    
    command = 'airflow dags test airflow_test_success_dag'
    result, output = run_docker_exec(command)

    assert_airflow_dag_completed(result)
    assert_airflow_dag_log_contains('Process executed successfully. Status: CompletedSuccessfully', output)
    assert_tm1server_log_contains("airflow_test_success executed")

def test_airflow_test_params_success_dag():
    
    command = 'airflow dags test airflow_test_params_success_dag'
    result, output = run_docker_exec(command)

    assert_airflow_dag_completed(result)
    assert_airflow_dag_log_contains('Process executed successfully. Status: CompletedSuccessfully', output)
    assert_tm1server_log_contains("airflow_test_success executed, testParam1:testParamValue")

def test_airflow_test_aborted_dag():
    
    command = 'airflow dags test airflow_test_aborted_dag'
    result, output = run_docker_exec(command)

    assert_airflow_dag_failed(result)
    assert_airflow_dag_log_contains('Process execution failed. Status: Aborted', output)
    assert_tm1server_log_contains("Process \"airflow_test_aborted\": : Execution was aborted. Error file: <tm1processerror_(.*)airflow_test_aborted.log> : Dimension \"Nemletezo\" not found.")

def test_ariflow_test_data_error_dag():
    
    command = 'airflow dags test airflow_test_data_error_dag'
    result, output = run_docker_exec(command)

    assert_airflow_dag_completed(result)
    assert_airflow_dag_log_contains('Process executed with minor errors. Status: HasMinorErrors', output)
    assert_tm1server_log_contains("Process \"airflow_test_data_error\":  finished executing with errors. Error file: <tm1processerror_(.*)_airflow_test_data_error.log> : Invalid key: Dimension Name: \"test1\", Element Name \(Key\): \"2022\"")

def test_airflow_test_timeout_dag():
    
    command = 'airflow dags test airflow_test_timeout_dag'
    result, output = run_docker_exec(command)

    assert_airflow_dag_failed(result)
    assert_airflow_dag_log_contains('Timeout after 3 seconds', output)
    assert_tm1server_log_contains("Process \"airflow_test_timeout\" executed by user \"Admin\"")


def test_airflow_test_execute_mdx():
    command = 'airflow dags test airflow_test_execute_mdx'
    result, output = run_docker_exec(command)

    assert_airflow_dag_failed(result)
    assert_airflow_dag_log_contains('test1 dim values:[\'test1_dim1\' \'test_dim2\' \'test1_dim3\']', output)

if __name__ == '__main__':
    pytest.main()