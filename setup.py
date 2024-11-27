from setuptools import setup, find_packages
import os
import re

def read_version():
    version_file = os.path.join(os.path.dirname(__file__), 'airflow_provider_tm1', '__init__.py')
    with open(version_file, 'r') as f:
        for line in f:
            if line.startswith('__version__'):
                delim = '"' if '"' in line else "'"
                return line.split(delim)[1]
    raise RuntimeError("Unable to find version string.")

setup(
    version=read_version(),
    packages=find_packages(exclude=["docs*", "tests*"]),
    include_package_data=True
)