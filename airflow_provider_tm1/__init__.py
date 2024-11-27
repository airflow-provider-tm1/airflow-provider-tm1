"""A TM1 provider package for Airflow"""
# Please note that this version gets overridden during publish_to_pypi workflow upon a new release with the defined release number.
__version__ = "0.0.10"

import os
import re

def update_version():
    version_file = os.path.join(os.path.dirname(__file__), '__init__.py')
    with open(version_file, 'r') as f:
        content = f.read()
    new_version = os.environ.get('VERSION')
    content_new = re.sub(r'__version__ = ["\'].*["\']', f'__version__ = "{new_version}"', content, 1)
    with open(version_file, 'w') as f:
        f.write(content_new)


def get_version():
    return __version__


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
        "version": [get_version()],
    }
