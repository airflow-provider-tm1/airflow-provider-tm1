"""
Example Airflow DAG demonstrating TM1 filesystem usage with ObjectStoragePath.

This exercises the native Airflow Object Storage API against TM1:
  - listing, writing, reading (binary + text)
  - stat / size / is_file
  - copy and glob
  - the TM1-specific name search

It relies on the TM1 filesystem being registered (via the provider's
``filesystems`` entry) so that ``tm1://`` URLs resolve through it.
"""

from datetime import datetime, timedelta

# Cross-version imports: airflow.providers.common.compat.sdk resolves to
# airflow.sdk (Airflow 3) or airflow.* (Airflow 2), so this DAG runs under both.
from airflow.providers.common.compat.sdk import DAG, ObjectStoragePath, dag, task

# Default arguments for the DAG
default_args = {
    "owner": "tm1-team",
    "depends_on_past": False,
    "start_date": datetime(2025, 1, 1),
    "email_on_failure": False,
    "email_on_retry": False,
    "retry_delay": timedelta(minutes=5),
}


@task(
    task_id="list_files",
)
def list_tm1_files(**context):
    """Task to list files in TM1"""
    tm1_dir = ObjectStoragePath("tm1://tm1_default@/")

    files = list(tm1_dir.iterdir())
    print(f"✅ Found {len(files)} files in tm1://.")
    for file_path in files:
        print(f"   - {file_path}")

    return [str(file_path) for file_path in files]


@task(
    task_id="write_tm1_file",
)
def write_tm1_file(**context):
    """Task to write a file to TM1 using the native Object Storage API"""
    test_file = ObjectStoragePath("tm1://test_file.txt", conn_id="tm1_default")
    test_file.write_bytes(b"This is a sample output file written to TM1.")
    print("✅ Sample output file written to TM1")

    # text mode + stat/size/is_file now work natively
    text_file = ObjectStoragePath("tm1://test_file.txt", conn_id="tm1_default")
    text_file.write_text("Hello TM1, from ObjectStoragePath!")
    st = text_file.stat()
    print(f"✅ stat: size={text_file.size()} bytes, is_file={text_file.is_file()}")
    return str(text_file)


@task(
    task_id="read_tm1_file",
)
def read_tm1_file(path: str, **context):
    """Task to read a file from TM1"""
    p = ObjectStoragePath(path, conn_id="tm1_default")
    assert p.exists(), "File does not exist in TM1"
    print(f"Reading file from TM1: {p}")
    content = p.read_text()
    print(f"✅ Read file from TM1: {len(content)} characters")
    return str(p)


@task(
    task_id="copy_and_search",
)
def copy_and_search(**context):
    """Task to copy a file and use the TM1-specific name search"""
    src = ObjectStoragePath("tm1://test_file.txt", conn_id="tm1_default")
    dst = ObjectStoragePath("tm1://test_file_copy.txt", conn_id="tm1_default")
    src.copy(dst)
    print(f"✅ Copied {src} -> {dst}")

    # native glob (resolved through the registered filesystem)
    matches = [str(p) for p in ObjectStoragePath("tm1://tm1_default@/").glob("test_file*")]
    print(f"✅ glob('test_file*') matched: {matches}")

    # TM1-specific substring search (NOT fsspec's recursive find)
    fs = dst.fs
    found = fs.search("copy", path="/")
    print(f"✅ TM1 search('copy') matched: {found}")

    return str(dst)


@dag(
    dag_id="tm1_filesystem_example",
    default_args=default_args,
    description="Example DAG using TM1 filesystem with ObjectStoragePath",
    catchup=False,
    tags=["tm1", "filesystem", "example"],
)
def tm1_filesystem_example_dag():
    """Example DAG demonstrating TM1 filesystem usage with ObjectStoragePath"""
    list_files_task = list_tm1_files()
    write_file_task = write_tm1_file()
    read_file_task = read_tm1_file(path=write_file_task)
    copy_and_search()
    read_tm1_file.override(task_id="read_tm1_file_expanded").expand(path=list_files_task)


tm1_filesystem_example_dag()
