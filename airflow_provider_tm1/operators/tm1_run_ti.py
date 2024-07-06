from typing import Optional

from airflow.models import BaseOperator
from airflow.utils.decorators import apply_defaults

from airflow_provider_tm1.hooks.tm1 import TM1Hook
from TM1py.Utils import format_url
import json
import time
from sqlalchemy import func
from TM1py.Exceptions.Exceptions import TM1pyTimeout, TM1pyVersionDeprecationException


class TM1RunTIOperator(BaseOperator):
    """
    This operator runs a TI process

    :param process_name: The TI process to run.
    :type process_name: str
    
    :param tm1_conn_id: The Airflow connection used for TM1 credentials.
    :type tm1_conn_id: str

    :param timeout: Given TM1 connection runs in async_request_mode, tm1_timeout defines the maximum time in seconds that the operator is  waiting for TM1 process to complete. Default is 1200 seconds.
    :type timeout: int

    :param cancel_at_timeout: Abort operation in TM1 when timeout is reached
    :type cancel_at_timeout: bool
    
    :param tm1_dry_run: in Dry mode the Operator will skip the execution. Default value is False.
    :type tm1_dry_run: bool

    :param tm1_params: TM1 TI process parameters to pass
    :type tm1_params: bool
    """

    @apply_defaults
    def __init__(
        self,
        process_name: str,
        tm1_conn_id: str = "tm1_default",
        timeout: int = 300,
        cancel_at_timeout : bool = False,
        tm1_dry_run: bool = False,
        tm1_params: dict = {},
        *args,
        **kwargs,
    ) -> None:

        super().__init__(*args, **kwargs)

        self.tm1_conn_id = tm1_conn_id
        self.timeout = timeout
        self.cancel_at_timeout = cancel_at_timeout
        self.tm1_dry_run = tm1_dry_run
        self.process_name = process_name
        self.tm1_params = tm1_params
        self.tm1_params['async_request_mode'] = True

    def execute(self, context: dict) -> None:
        tm1_hook = TM1Hook(tm1_conn_id=self.tm1_conn_id)

        tm1 = tm1_hook.get_conn()

        if not self.tm1_dry_run:
           
            url, job_id = execute_aync(tm1, process_name=self.process_name, timeout=self.timeout, cancel_at_timeout=self.cancel_at_timeout, **self.tm1_params)
            print("async job_id " + job_id)

            for wait in tm1._tm1_rest.wait_time_generator(self.timeout):
                response = tm1._tm1_rest.retrieve_async_response(job_id)
                if response.status_code in [200, 201]:
                    break
                time.sleep(wait)

             # all wait times consumed and still no 200
            if response.status_code not in [200, 201]:
                if self.cancel_at_timeout:
                    cancel_async_operation(tm1, job_id)
                raise TM1pyTimeout(method='POST', url=url, timeout=self.timeout)

            # response transformation necessary in TM1 < v11. Not required for v12
            if response.content.startswith(b"HTTP/"):
                response = tm1._tm1_rest.build_response_from_binary_response(response.content)
            else:
                # In v12 status_code must be set explicitly, as it is 200 by default
                response.status_code = int(response.headers['asyncresult'])

            # all wait times consumed and still no 200
            if response.status_code not in [200, 201]:
                print("Time Out")

            success, status, error_log_file = parse_ti_response(response)
            handle_tm1_process_result(error_log_file, status)


        else:
            print("Triggering TM1 " + self.process_name + " in dry-run mode with timeout " + str(self.tm1_timeout) + " with parameters ", self.tm1_ti_params)

def execute_aync(tm1, process_name: str, timeout: int, cancel_at_timeout: bool, **kwargs):
    additional_header = {'Prefer': 'respond-async'}

    url = format_url("/api/v1/Processes('{}')/tm1.ExecuteWithReturn?$expand=*", process_name)
    parameters = dict()
    if kwargs:
        parameters = {"Parameters": []}
        for parameter_name, parameter_value in kwargs.items():
            parameters["Parameters"].append({"Name": parameter_name, "Value": parameter_value})

    response = tm1._tm1_rest.POST(
        url=url,
        data=json.dumps(parameters, ensure_ascii=False),
        timeout=timeout,
        cancel_at_timeout=cancel_at_timeout,
        headers=additional_header,
        **kwargs)

    tm1._tm1_rest.verify_response(response=response)

    if 'Location' not in response.headers or "'" not in response.headers['Location']:
        raise ValueError(f"Failed to retrieve async_id from request {func.__name__} '{url}'")

    async_id = response.headers.get('Location').split("'")[1]

    return url, async_id

def cancel_async_operation(tm1, async_id: str, **kwargs):
    url = tm1._tm1_rest._base_url + f"/_async('{async_id}')"
    response = tm1._tm1_rest._s.delete(url, verify=False, **kwargs)
    tm1._tm1_rest.verify_response(response)
    print("Response: " + response.text)

def parse_ti_response(response):
    execution_summary = response.json()
    success = execution_summary["ProcessExecuteStatusCode"] == "CompletedSuccessfully"
    status = execution_summary["ProcessExecuteStatusCode"]
    error_log_file = None if execution_summary["ErrorLogFile"] is None else execution_summary["ErrorLogFile"][
        "Filename"]
    return success, status, error_log_file


def handle_tm1_process_result(error_log_file, status):
    if status == 'CompletedSuccessfully':
        print("Process executed successfully. Status: " + status)
    elif status == 'HasMinorErrors':
        print( "Process executed with minor errors. Status: " + status + ". Path to error log file: " + error_log_file)
    elif status == 'Aborted':
        raise Exception("Process execution failed. Status: " + status + ". Path to error log file: " + error_log_file)
    else:
        raise Exception("Process execution could have failed, Unknown status: " + status + ". Path to error log file: " + error_log_file)