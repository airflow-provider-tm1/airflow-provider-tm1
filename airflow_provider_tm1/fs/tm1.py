import logging

from fsspec import AbstractFileSystem
from fsspec.spec import AbstractBufferedFile
from TM1py import TM1Service
from TM1py.Services.FileService import FileService
from TM1py.Utils.Utils import verify_version

from airflow_provider_tm1.hooks.tm1 import TM1Hook

log = logging.getLogger(__name__)


def get_fs(conn_id: str | None = None, storage_options: dict | None = None) -> AbstractFileSystem:
    """Airflow Object Storage entry point.

    Returns an fsspec filesystem for the ``tm1`` scheme. Discovered by Airflow via the
    provider's ``filesystems`` entry in ``get_provider_info``; must expose a two-arg
    signature so that ``storage_options`` can be forwarded from ``ObjectStoragePath``.
    """
    if conn_id is None:
        conn_id = TM1Hook.default_conn_name
    tm1_hook = TM1Hook(tm1_conn_id=conn_id)
    tm1_service = tm1_hook.get_conn()
    return TM1BlobStorage(tm1_service=tm1_service, **(storage_options or {}))


# ---------------------------------------------------------------------------
# Version capabilities
# ---------------------------------------------------------------------------


class TM1VersionCapabilities:
    """Centralised TM1 version capability detection.

    TM1 v11 (``Blobs``) and v12 (``Files``) handle file storage in fundamentally
    different ways. Rather than scattering ``verify_version`` calls throughout the
    filesystem, all version-dependent behaviour is resolved once here and consumed
    by the filesystem and file classes.

    ============================  =========================  ==============================
    Capability                    v11 (``Blobs``)            v12 (``Files``)
    ============================  =========================  ==============================
    Content path                  ``Blobs``                  ``Files``
    Namespace                     flat (no subfolders)       subfolders supported
    Upload                        single ``PUT``             multipart upload (MPU)
    Path refinement               strip leading ``/``        unchanged
    ============================  =========================  ==============================
    """

    #: Minimum version that supports subfolders (also the Files/Blobs split).
    SUBFOLDER_REQUIRED_VERSION: str = FileService.SUBFOLDER_REQUIRED_VERSION
    #: Minimum version that supports multipart upload.
    MPU_REQUIRED_VERSION: str = FileService.MPU_REQUIRED_VERSION

    def __init__(self, version: str):
        self.version = version
        self.is_v12: bool = verify_version(self.SUBFOLDER_REQUIRED_VERSION, version)

    # -- capability properties ---------------------------------------------

    @property
    def supports_subfolders(self) -> bool:
        """Whether the server supports folder paths (v12 only)."""
        return self.is_v12

    @property
    def supports_mpu(self) -> bool:
        """Whether the server supports multipart upload (v12 only)."""
        return self.is_v12

    @property
    def content_path(self) -> str:
        """The TM1 OData content container: ``Files`` (v12) or ``Blobs`` (v11)."""
        return "Files" if self.is_v12 else "Blobs"

    # -- path handling ------------------------------------------------------

    def refine_path(self, path: str) -> str:
        """Normalise a path for the server version.

        v12 keeps paths as-is (subfolders allowed). v11 uses a flat namespace, so a
        path with a single leading ``/`` (e.g. ``/myfile.txt``) is stripped to
        ``myfile.txt``; paths with no leading ``/`` or with ``//`` are returned
        unchanged (the latter being an absolute/share path).
        """
        if self.is_v12:
            return path

        if not path.startswith("/"):
            return path
        if not path.startswith("//"):
            return path[1:]
        return path

    # -- factory ------------------------------------------------------------

    def buffered_file_cls(self):
        """Return the appropriate buffered-file class for this server version.

        v12 returns :class:`TM1FileV12` which exposes multipart-upload extension
        points; v11 returns :class:`TM1FileV11` which uses a simple single-PUT
        write-back. Override or extend these for custom streaming behaviour.
        """
        return TM1FileV12 if self.is_v12 else TM1FileV11


def _normalize_path(path: str) -> str:
    """Normalise a path so it can be compared/joined consistently.

    Strips a leading protocol prefix if present, collapses redundant leading slashes
    to a single one, and treats an empty path as root (``/``).
    """
    if not path:
        return "/"

    # drop any "tm1://" prefix (and an optional userinfo@host) that may leak through
    if "://" in path:
        path = path.split("://", 1)[1]
        if "@" in path:
            path = path.split("@", 1)[1]

    # collapse multiple leading slashes into one
    while path.startswith("//"):
        path = path[1:]

    if not path.startswith("/"):
        path = "/" + path

    return path or "/"


# ---------------------------------------------------------------------------
# Buffered file classes
# ---------------------------------------------------------------------------


class TM1BufferedFile(AbstractBufferedFile):
    """Base buffered, file-like view over a TM1 blob/document.

    Buffering, text-mode wrapping, flush-on-close and read caching are provided by
    :class:`fsspec.spec.AbstractBufferedFile`. Subclasses implement the three required
    hooks (``_initiate_upload``, ``_upload_chunk``, ``_fetch_range``) with version-
    appropriate write semantics.

    Read path: TM1py has no range request API, so the whole blob is fetched once and
    sliced on demand (see :meth:`_fetch_range`).
    """

    def __init__(self, fs, path, mode="rb", block_size="default", autocommit=True, cache_type="readahead", **kwargs):
        super().__init__(
            fs,
            path,
            mode=mode,
            block_size=block_size,
            autocommit=autocommit,
            cache_type=cache_type,
            **kwargs,
        )
        # cache for read mode: the full file content.
        self._data: bytes | None = None

    # -- read path (shared) ------------------------------------------------

    def _fetch_range(self, start: int, end: int) -> bytes:
        """Return ``data[start:end]``. TM1py has no range request, so fetch once."""
        if self._data is None:
            log.debug("Fetching TM1 file content for %s", self.path)
            self._data = self.fs._tm1.files.get(self.path)
        return self._data[start:end]


class TM1FileV11(TM1BufferedFile):
    """Buffered file for TM1 v11 (``Blobs``).

    v11 supports only a single ``PUT`` upload with no multipart, so writes accumulate
    in the in-memory buffer and the full content is pushed once on the final flush
    via ``update_or_create`` (which selects the non-MPU path on v11).
    """

    def _initiate_upload(self):
        """No-op: v11 does a single PUT at upload time."""
        log.debug("Initiating v11 upload for %s", self.path)

    def _upload_chunk(self, final=False):
        """Defer every intermediate chunk; push the whole buffer on final flush."""
        if not final:
            return True

        data = self.buffer.getvalue()
        log.info("Writing %d bytes to TM1 v11 path: %s", len(data), self.path)
        self.fs._tm1.files.update_or_create(self.path, data)
        return True


class TM1FileV12(TM1BufferedFile):
    """Buffered file for TM1 v12 (``Files``).

    v12 supports multipart upload (MPU) and subfolders. Currently writes buffer fully
    and are pushed on the final flush via ``update_or_create`` (which auto-selects MPU
    on v12). True chunked streaming can be added by implementing the MPU extension
    points below — see :meth:`_initiate_mpu`, :meth:`_upload_part`,
    :meth:`_complete_mpu`.

    Enhancement buffer — MPU streaming extension points:

    To stream large files in chunks instead of buffering fully, override::

        _initiate_upload()   -> call _initiate_mpu() to start an MPU session
        _upload_chunk(final) -> call _upload_part(buffer_chunk) for each block
        close()/flush(final) -> call _complete_mpu() to finalise

    The TM1py MPU flow is::

        POST   <content_url>/mpu.CreateMultipartUpload       -> UploadID
        POST   <content_url>/!uploads('{UploadID}')/Parts     -> PartNumber, ETag
        POST   <content_url>/!uploads('{UploadID}')/mpu.Complete
    """

    def _initiate_upload(self):
        """No-op for the current buffer-then-upload strategy.

        When implementing MPU streaming, start the upload session here::

            self._upload_id = self._initiate_mpu()
        """
        log.debug("Initiating v12 upload for %s", self.path)

    def _upload_chunk(self, final=False):
        """Defer intermediate chunks; push the whole buffer on the final flush.

        When implementing MPU streaming, push each block as an MPU part here and
        call :meth:`_complete_mpu` when ``final`` is ``True``.
        """
        if not final:
            return True

        data = self.buffer.getvalue()
        log.info("Writing %d bytes to TM1 v12 path: %s", len(data), self.path)
        self.fs._tm1.files.update_or_create(self.path, data)
        return True

    # -- MPU streaming extension points (stubs for future enhancement) -----

    def _initiate_mpu(self) -> str:
        """Start a multipart upload and return the ``UploadID``.

        Not yet wired into the write path. When enabled, call this from
        :meth:`_initiate_upload` and cache the returned ID on ``self``.
        """
        raise NotImplementedError("MPU streaming is reserved for future enhancement")

    def _upload_part(self, part_data: bytes) -> tuple[int, str]:
        """Upload one chunk as an MPU part.

        :return: ``(part_number, etag)`` from the server response.
        Not yet wired into the write path.
        """
        raise NotImplementedError("MPU streaming is reserved for future enhancement")

    def _complete_mpu(self, parts: list[tuple[int, str]]) -> None:
        """Finalise a multipart upload given the list of ``(part_number, etag)``.

        Not yet wired into the write path.
        """
        raise NotImplementedError("MPU streaming is reserved for future enhancement")


# Backward-compatible alias for the previous public class name.
TM1Blob = TM1BufferedFile


# ---------------------------------------------------------------------------
# Filesystem
# ---------------------------------------------------------------------------


class TM1BlobStorage(AbstractFileSystem):
    """A file system for TM1 that allows interaction with TM1 objects as files.

    Implements the fsspec ``AbstractFileSystem`` contract that Airflow's
    ``ObjectStoragePath`` relies on. The keystone methods (``ls``, ``_rm``,
    ``cp_file``, ``_open``) are implemented here; the rest (``exists``, ``isdir``,
    ``isfile``, ``size``, ``walk``, ``find``, ``glob``, ``expand_path``, ``rm``,
    ``copy``, ``move``, ``get``, ``put``, ``cat_file``, ``ukey``, ``checksum``,
    ``read_block``) are inherited and derive their behaviour from the keystones.

    Version handling is centralised in a :class:`TM1VersionCapabilities` instance
    (``self._caps``); the filesystem delegates all version-dependent decisions
    (path refinement, subfolder/mkdir support, file-class selection) to it.
    """

    protocol = ("tm1",)

    def __init__(self, tm1_service: TM1Service, **kwargs):
        super().__init__(**kwargs)
        self._tm1 = tm1_service
        self._caps = TM1VersionCapabilities(tm1_service.version)

    # -- keystone: list -----------------------------------------------------

    def ls(self, path, detail=True, **kwargs):
        """List files in a given TM1 path.

        :param detail: if ``True`` (default), return a list of dicts with at least
            ``name`` (full path), ``size`` and ``type``; if ``False``, return a list
            of full paths as strings.
        """
        self._assert_tm1()
        normalized = _normalize_path(path)
        refined_path = self._caps.refine_path(normalized)
        log.info("Listing files in path: %s", refined_path)

        if normalized == "/":
            names = self._tm1.files.get_all_names()
        else:
            # TM1py expects the folder path without a leading "/" for get_all_names
            folder = refined_path.lstrip("/")
            names = self._tm1.files.get_all_names(folder)

        entries = []
        base = "" if normalized == "/" else normalized.rstrip("/")
        for name in names:
            full = f"{base}/{name}" if base else f"/{name}"
            entries.append({"name": full, "size": None, "type": "file"})

        if not detail:
            return [e["name"] for e in entries]
        return entries

    # -- info / stat (overridden for an accurate single-file size) ----------

    def info(self, path, **kwargs):
        """Give details of the entry at ``path``.

        For the root, returns a directory entry. For a single file, fetches its real
        size (one round trip) so that ``ObjectStoragePath.size()`` / ``stat()`` are
        accurate. Raises :class:`FileNotFoundError` if the path does not exist.
        """
        self._assert_tm1()
        normalized = _normalize_path(path)

        if normalized == "/":
            return {"name": "", "size": 0, "type": "directory"}

        refined_path = self._caps.refine_path(normalized)
        if not self._tm1.files.exists(refined_path):
            raise FileNotFoundError(f"File {refined_path} does not exist in TM1.")

        try:
            size = len(self._tm1.files.get(refined_path))
        except Exception:
            # if the content fetch fails, fall back to unknown size rather than crashing
            size = None
        return {"name": normalized, "size": size, "type": "file"}

    # -- keystone: open -----------------------------------------------------

    def _open(self, path, mode="rb", block_size=None, autocommit=True, cache_options=None, **kwargs):
        """Return a buffered, file-like object for ``path``.

        The concrete file class is chosen by :class:`TM1VersionCapabilities` so that
        v11 (single-PUT) and v12 (MPU-capable) get version-appropriate write semantics.
        """
        self._assert_tm1()

        if mode not in ("rb", "wb", "ab", "xb"):
            raise ValueError(f"Unsupported mode '{mode}'. Supported modes: rb, wb, ab, xb.")

        normalized = _normalize_path(path)
        refined_path = self._caps.refine_path(normalized)

        if mode == "rb" and not self._tm1.files.exists(refined_path):
            raise FileNotFoundError(f"File {refined_path} does not exist in TM1.")
        if mode == "xb" and self._tm1.files.exists(refined_path):
            raise FileExistsError(f"File {refined_path} already exists in TM1.")

        file_cls = self._caps.buffered_file_cls()
        return file_cls(
            self,
            refined_path,
            mode=mode,
            block_size=block_size,
            autocommit=autocommit,
            cache_options=cache_options,
            **kwargs,
        )

    # -- keystone: remove ---------------------------------------------------

    def _rm(self, path):
        """Remove a single file in TM1."""
        self._assert_tm1()
        refined_path = self._caps.refine_path(_normalize_path(path))
        log.info("Removing file: %s", refined_path)
        self._tm1.files.delete(refined_path)

    # -- keystone: copy -----------------------------------------------------

    def cp_file(self, path1, path2, **kwargs):
        """Copy a single file from ``path1`` to ``path2``.

        TM1 has no server-side copy, so the content is read and re-uploaded.
        """
        self._assert_tm1()
        src = self._caps.refine_path(_normalize_path(path1))
        dst = self._caps.refine_path(_normalize_path(path2))
        log.info("Copying %s -> %s", src, dst)
        data = self._tm1.files.get(src)
        self._tm1.files.update_or_create(dst, data)

    # -- directories (v12 only) --------------------------------------------

    def mkdir(self, path, create_parents=True, **kwargs):
        """Create a directory. On TM1 v11 this is a no-op (flat namespace)."""
        self._assert_tm1()
        normalized = _normalize_path(path)
        if normalized == "/":
            return

        if not self._caps.supports_subfolders:
            log.debug("mkdir is a no-op on TM1 < v12 (flat namespace): %s", normalized)
            return

        if create_parents:
            self.makedirs(normalized, exist_ok=kwargs.get("exist_ok", False))
        else:
            refined = self._caps.refine_path(normalized).lstrip("/")
            if self._tm1.files.exists(refined):
                raise FileExistsError(f"{normalized} already exists in TM1")
            self._tm1.files.create_folder(refined)

    def makedirs(self, path, exist_ok=False):
        """Recursively create directories. On TM1 v11 this is a no-op."""
        self._assert_tm1()
        normalized = _normalize_path(path)
        if normalized == "/":
            return

        if not self._caps.supports_subfolders:
            log.debug("makedirs is a no-op on TM1 < v12 (flat namespace): %s", normalized)
            return

        refined = self._caps.refine_path(normalized).lstrip("/")
        if not exist_ok and self._tm1.files.exists(refined):
            raise FileExistsError(f"{normalized} already exists in TM1")
        # TM1py's create_folder already creates intermediate folders recursively on v12
        self._tm1.files.create_folder(refined)

    # -- TM1-specific search (NOT fsspec's recursive find) -----------------

    def search(self, *name_contains, path: str = "", name_contains_operator: str = "and"):
        """Search for TM1 files whose name contains the given substrings.

        This is a TM1-specific convenience backed by ``FileService.search_string_in_name``
        and is intentionally *not* named ``find``: fsspec's ``find`` has a different
        contract (recursive listing of ``path``) and overloading it breaks ``glob``,
        ``walk``, ``expand_path`` and directory copy.

        :param name_contains: one or more substrings to match (case-insensitive).
        :param name_contains_operator: ``"and"`` (default) or ``"or"``.
        :param path: folder to search in (empty for root).
        :return: list of matching file names.
        """
        if not name_contains:
            raise ValueError("At least one name_contains parameter is required.")

        self._assert_tm1()
        refined_path = self._caps.refine_path(_normalize_path(path))
        return self._tm1.files.search_string_in_name(
            name_contains=name_contains,
            path=refined_path,
            name_contains_operator=name_contains_operator,
        )

    # -- helpers ------------------------------------------------------------

    def _assert_tm1(self):
        if not self._tm1:
            raise ValueError("TM1Service instance is not registered.")
