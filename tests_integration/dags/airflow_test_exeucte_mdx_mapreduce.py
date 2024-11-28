from datetime import timedelta
from time import sleep

import pandas as pd
from airflow import DAG
from airflow.utils.dates import days_ago
from airflow.decorators import task

from airflow_provider_tm1.operators.tm1_mdx_query import TM1MDXQueryOperator

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email': ['airflow@example.com'],
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 0,
    'retry_delay': timedelta(minutes=5)
}


def parse_and_filter(df: pd.DataFrame):
    print("test1 dim values:" + str(df.test1.values))
    print("test2 dim values:" + str(df.test2.values))
    return df


with DAG(
        'airflow_test_execute_mdx_mapreduce',
        default_args=default_args,
        schedule_interval=None,
        start_date=days_ago(1),
        tags=[],
        catchup=False,
        max_active_runs=1
) as dag:

    @task
    def reduce(dataframes):
        # Returning big dataframes in parse_and_filter and joining them in a list might have performance degration. 
        # If the purpose of reduce() is merely to wait for all the chunks to complete, parse_and_filter should return only a flag or maybe the size of dataframe, but not the entire dataframe
        # However, it might still have acceptable performance even when returning entire mapped dataframes if they are relatively small (and fit to xcom capabilities)
        print("Returned dataframe size: " + str(len(dataframes)))


    dataframes = TM1MDXQueryOperator.partial(
        task_id="map",
        tm1_conn_id='tm1_conn',
        post_callable=parse_and_filter
    ).expand(
        mdx=["""
           SELECT 
           {[test2].[test2].Members} 
           ON COLUMNS , 
           {[test1].[test1].Members} 
           ON ROWS 
           FROM [test1] 
           """,

           """
           SELECT 
           {[test2].[test2].Members} 
           ON COLUMNS , 
           {[test1].[test1].Members} 
           ON ROWS 
           FROM [test1] 
           """],
    )

    reduce(dataframes.output)


