from .tm1 import get_fs, TM1BlobStorage
from fsspec.registry import register_implementation
import logging

log = logging.getLogger(__name__)

schemes = ["tm1"]

try:
    register_implementation('tm1', TM1BlobStorage)
    log.info("TM1 filesystem registered successfully for scheme 'tm1'")
except Exception as e:
    log.error(f"Failed to register TM1 filesystem: {e}")

__all__ = ['get_fs', 'TM1BlobStorage', 'schemes']
