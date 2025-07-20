from fsspec import AbstractFileSystem 
from TM1py import TM1Service
import io
from airflow_provider_tm1.hooks.tm1 import TM1Hook 
import logging 

from fsspec import AbstractFileSystem 
from TM1py import TM1Service
import io
from TM1py.Utils.Utils import verify_version
from TM1py.Services.FileService import FileService


log = logging.getLogger(__name__)

def get_fs(conn_id: str | None = None, storage_options: dict | None = None) -> AbstractFileSystem:
    if conn_id is None:
        conn_id = TM1Hook.default_conn_name
    tm1_hook = TM1Hook(tm1_conn_id=conn_id)
    tm1_service = tm1_hook.get_conn()
    return TM1BlobStorage(tm1_service=tm1_service, **(storage_options or {}))

def _refine_path_for_v11(path: str, tm1_service: TM1Service) -> str:
    """Refine the path for TM1 version 11 and above."""
    
    if verify_version(required_version=FileService.SUBFOLDER_REQUIRED_VERSION, version=tm1_service.version):
        #* v12 may allow subfolders, so we do not need to change the path
        return path 
    
    if not path.startswith('/'):
        #* If the path does not start with '/', we assume it is a absolute path
        return path

    if not path.startswith('//'):
        #* only care about paths that start with a single '/', like '/myfile.txt'
        return path[1:]
    
    return path

class TM1Blob(io.BytesIO):
    def __init__(self, buffer: bytes, tm1_service: TM1Service, path: str, mode='rb'):
        super().__init__(buffer)
        self._tm1 = tm1_service
        self._path = path
        self._mode = mode
    
    def __exit__(self, exc_type, exc_value, traceback):
        """Context manager exit method."""
        self._tm1.files.update_or_create(self._path, self.getvalue())

class TM1BlobStorage(AbstractFileSystem):
    """A file system for TM1 that allows interaction with TM1 objects as files."""
    protocol = ('tm1', )
    def __init__(self, tm1_service: TM1Service, **kwargs):
        super().__init__(**kwargs)
        self._tm1 = tm1_service
        
    def exists(self, path, **kwargs):
        """Check if a file exists in TM1."""
        assert self._tm1, "TM1Service instance is not registered."
        refined_path = _refine_path_for_v11(path, self._tm1)
        log.info(f"Checking existence of path: {refined_path}")
        return self._tm1.files.exists(refined_path)

    def ls(self, path, **kwargs):
        """List files in a given TM1 path."""
        assert self._tm1, "TM1Service instance is not registered."
        
        log.info(f"Listing files in path: {path}")
        if not self._tm1:
            raise ValueError("TM1Service instance is not registered. Use register_tm1_service() to set it.")
        if path == '/':
            return self._tm1.files.get_all_names()
        
        refined_path = _refine_path_for_v11(path, self._tm1)
        return self._tm1.files.get_all_names(refined_path)

    def open(self, path, mode='rb', **kwargs):
        """Open a file in TM1."""
        assert self._tm1, "TM1Service instance is not registered."
        log.info(f"Opening file: {path} in mode: {mode}")
        refined_path = _refine_path_for_v11(path, self._tm1)
        if not self._tm1:
            raise ValueError("TM1Service instance is not registered. Use register_tm1_service() to set it.")
        if mode not in ['rb', 'wb']:
            raise ValueError("Mode must be 'rb' or 'wb'.")

        if not self._tm1.files.exists(refined_path):
            if mode == 'rb':
                raise FileNotFoundError(f"File {refined_path} does not exist in TM1.")
            data = b''
        else:
            data = self._tm1.files.get(refined_path)

        return TM1Blob(data, self._tm1, refined_path, mode)

    def rm(self, path, **kwargs):
        """Remove a file in TM1."""
        assert self._tm1, "TM1Service instance is not registered."
        refined_path = _refine_path_for_v11(path, self._tm1)
        log.info(f"Removing file: {refined_path}")
        if not self._tm1:
            raise ValueError("TM1Service instance is not registered. Use register_tm1_service() to set it.")
        self._tm1.files.delete(refined_path)

    def find(self, *name_contains, path: str = '.', name_contains_operator: str = 'and'):
        """Find files in TM1 based on name_contains criteria."""
        if not name_contains:
            raise ValueError("At least one name_contains parameter is required.")
        
        assert self._tm1, "TM1Service instance is not registered."
        refined_path = _refine_path_for_v11(path, self._tm1)
        return self._tm1.files.search_string_in_name(name_contains=name_contains,
                                              path=refined_path,
                                              name_contains_operator=name_contains_operator)

    def __del__(self):
        """Ensure the TM1 service is properly closed when the file system is deleted."""
        if self._tm1:
            self._tm1.logout()
            self._tm1 = None
