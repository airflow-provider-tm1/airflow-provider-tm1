"""Integration test DAG for the TM1 filesystem (native Object Storage API).

Mirrors ``example_dags/tm1_filesystem_example_dag.py`` but uses the ``tm1_conn``
connection id that the integration stack provisions, so it runs inside the
docker-compose worker. Exercises ls / write / read / stat / size / copy / glob /
search against the registered ``tm1://`` filesystem.
"""

from datetime import datetime, timedelta

from airflow.providers.common.compat.sdk import DAG, ObjectStoragePath, dag, task

CONN_ID = "tm1_conn"

default_args = {
    "owner": "tm1-team",
    "depends_on_past": False,
    "start_date": datetime(2025, 1, 1),
    "email_on_failure": False,
    "email_on_retry": False,
    "retry_delay": timedelta(minutes=5),
}


@task(task_id="write_tm1_file")
def write_tm1_file(**context):
    """Write a file to TM1 using the native Object Storage API."""
    test_file = ObjectStoragePath("tm1://test_file.txt", conn_id=CONN_ID)
    test_file.write_bytes(b"This is a sample output file written to TM1.")
    print("✅ Sample output file written to TM1")

    # text mode + stat/size/is_file now work natively
    text_file = ObjectStoragePath("tm1://test_file.txt", conn_id=CONN_ID)
    text_file.write_text("Hello TM1, from ObjectStoragePath!")
    st = text_file.stat()
    print(f"✅ stat: size={text_file.size()} bytes, is_file={text_file.is_file()}")
    return str(text_file)


@task(task_id="read_tm1_file")
def read_tm1_file(path: str, **context):
    """Read a file from TM1."""
    p = ObjectStoragePath(path, conn_id=CONN_ID)
    assert p.exists(), "File does not exist in TM1"
    content = p.read_text()
    print(f"✅ Read file from TM1: {len(content)} characters")
    return str(p)


@task(task_id="copy_and_search")
def copy_and_search(**context):
    """Copy a file and use the TM1-specific name search."""
    src = ObjectStoragePath("tm1://test_file.txt", conn_id=CONN_ID)
    dst = ObjectStoragePath("tm1://test_file_copy.txt", conn_id=CONN_ID)
    src.copy(dst)
    print(f"✅ Copied {src} -> {dst}")

    # native glob (resolved through the registered filesystem)
    matches = [str(p) for p in ObjectStoragePath(f"tm1://{CONN_ID}@/").glob("test_file*")]
    print(f"✅ glob('test_file*') matched: {matches}")

    # TM1-specific substring search (NOT fsspec's recursive find)
    found = dst.fs.search("copy", path="/")
    print(f"✅ TM1 search('copy') matched: {found}")

    return str(dst)


@dag(
    dag_id="tm1_filesystem_example",
    default_args=default_args,
    description="Integration DAG using TM1 filesystem with ObjectStoragePath",
    catchup=False,
    tags=["tm1", "filesystem", "example"],
)
def tm1_filesystem_example_dag():
    write_file_task = write_tm1_file()
    read_file_task = read_tm1_file(path=write_file_task)
    copy_and_search()


tm1_filesystem_example_dag()
