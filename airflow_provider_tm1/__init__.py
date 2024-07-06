"""A TM1 provider package for Airflow"""
__version__ = "0.0.10"


def get_provider_info():
    return {
        "package-name": "airflow-provider-tm1",
        "name": "TM1 Airflow Provider",
        "description": "An Apache Airflow provider for TM1",
        "connection-types": [
            {
                "connection-type": "tm1",
                "hook-class-name": "airflow_provider_tm1.hooks.tm1.TM1Hook",
            },
        ],
        "version": [__version__],
    }
