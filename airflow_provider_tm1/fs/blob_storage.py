from fsspec import AbstractFileSystem 
from TM1py import TM1Service
import io 


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
        
    def ls(self, path, **kwargs):
        """List files in a given TM1 path."""
        if not self._tm1:
            raise ValueError("TM1Service instance is not registered. Use register_tm1_service() to set it.")
        if path == '/':
            return self._tm1.files.get_all_names()
        
        return self._tm1.files.get_all_names(path)

    def open(self, path, mode='rb', **kwargs):
        """Open a file in TM1."""
        if not self._tm1:
            raise ValueError("TM1Service instance is not registered. Use register_tm1_service() to set it.")
        if mode not in ['rb', 'wb']:
            raise ValueError("Mode must be 'rb' or 'wb'.")
        
        if not self._tm1.files.exists(path):
            if mode == 'rb':
                raise FileNotFoundError(f"File {path} does not exist in TM1.")
            data = b''
        else:
            data = self._tm1.files.get(path)
            
        return TM1Blob(data, self._tm1, path, mode)

    def rm(self, path, **kwargs):
        """Remove a file in TM1."""
        if not self._tm1:
            raise ValueError("TM1Service instance is not registered. Use register_tm1_service() to set it.")
        self._tm1.files.delete(path)
