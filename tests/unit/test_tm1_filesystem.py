"""Unit tests for the TM1 filesystem (fsspec / Airflow ObjectStorage contract).

These tests use a mocked TM1py service so they run without a docker stack. They
verify that ``TM1BlobStorage`` satisfies the fsspec ``AbstractFileSystem`` contract
that ``airflow.io.path.ObjectStoragePath`` relies on, for both TM1 v11 (Blobs,
single-PUT, flat namespace) and v12 (Files, MPU, subfolders).
"""

from __future__ import annotations

import inspect

import pytest
from fsspec import AbstractFileSystem

from airflow_provider_tm1.fs import (
    TM1Blob,
    TM1BlobStorage,
    TM1BufferedFile,
    TM1FileV11,
    TM1FileV12,
    TM1VersionCapabilities,
    get_fs,
    schemes,
)
from airflow_provider_tm1.fs.tm1 import _normalize_path


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_mock_tm1(version: str):
    """Build a MagicMock that behaves like TM1py's TM1Service for one version.

    Returns ``(fs, tm1, names, contents)``. v12 keeps leading slashes in refined
    paths; v11 (flat namespace) strips them. The mock's ``files.exists``/
    ``files.get`` keys reflect that so the same code path exercises both version
    behaviours.
    """
    from unittest.mock import MagicMock

    flat = version == "11.4.0"  # v11: flat -> no leading slash on stored names
    names = ["alpha.csv", "beta.csv", "gamma.json"]
    contents = {
        ("alpha.csv" if flat else "/alpha.csv"): b"hello alpha",  # 11 bytes
        ("beta.csv" if flat else "/beta.csv"): b"betabetabeta",  # 12 bytes
        ("gamma.json" if flat else "/gamma.json"): b"{}",  # 2 bytes
    }

    tm1 = MagicMock()
    tm1.version = version

    def fake_get_all_names(path="", **kwargs):
        # TM1py returns bare file names; for a subfolder it returns names in it.
        if path in ("", "/"):
            return list(names)
        return []

    def fake_get(name, **kwargs):
        return contents[name]

    def fake_exists(name, **kwargs):
        return name in contents

    tm1.files.get_all_names.side_effect = fake_get_all_names
    tm1.files.get.side_effect = fake_get
    tm1.files.exists.side_effect = fake_exists
    fs = TM1BlobStorage(tm1_service=tm1)
    return fs, tm1, names, contents


@pytest.fixture
def fs_v11():
    return _make_mock_tm1("11.4.0")


@pytest.fixture
def fs_v12():
    return _make_mock_tm1("12.0.0")


# ---------------------------------------------------------------------------
# Module / registration contract
# ---------------------------------------------------------------------------


class TestModuleContract:
    def test_schemes(self):
        assert schemes == ["tm1"]

    def test_get_fs_two_arg_signature(self):
        """Airflow's loader inspects get_fs's signature for storage_options."""
        params = list(inspect.signature(get_fs).parameters)
        assert params == ["conn_id", "storage_options"]

    def test_exports(self):
        import airflow_provider_tm1.fs as fs

        for name in [
            "get_fs",
            "schemes",
            "TM1BlobStorage",
            "TM1BufferedFile",
            "TM1FileV11",
            "TM1FileV12",
            "TM1Blob",
            "TM1VersionCapabilities",
        ]:
            assert hasattr(fs, name), name

    def test_protocol(self):
        assert TM1BlobStorage.protocol == ("tm1",)

    def test_tm1blob_is_backward_compat_alias(self):
        assert TM1Blob is TM1BufferedFile

    def test_find_is_inherited_not_overridden(self):
        """Overloading find() breaks glob/walk/expand_path; it must be inherited."""
        assert "find" in AbstractFileSystem.__dict__
        assert "find" not in TM1BlobStorage.__dict__


# ---------------------------------------------------------------------------
# Version capabilities
# ---------------------------------------------------------------------------


class TestVersionCapabilities:
    def test_v11_capabilities(self):
        caps = TM1VersionCapabilities("11.4.0")
        assert caps.is_v12 is False
        assert caps.supports_subfolders is False
        assert caps.supports_mpu is False
        assert caps.content_path == "Blobs"
        assert caps.buffered_file_cls() is TM1FileV11

    def test_v12_capabilities(self):
        caps = TM1VersionCapabilities("12.0.0")
        assert caps.is_v12 is True
        assert caps.supports_subfolders is True
        assert caps.supports_mpu is True
        assert caps.content_path == "Files"
        assert caps.buffered_file_cls() is TM1FileV12

    @pytest.mark.parametrize(
        "version,path,expected",
        [
            # v11 strips a single leading slash (flat namespace)
            ("11.4.0", "/myfile.txt", "myfile.txt"),
            ("11.4.0", "folder/file", "folder/file"),  # no leading slash -> unchanged
            ("11.4.0", "//share", "//share"),  # double slash -> absolute, kept
            # v12 keeps paths as-is (subfolders allowed)
            ("12.0.0", "/myfile.txt", "/myfile.txt"),
            ("12.0.0", "/folder/file", "/folder/file"),
        ],
    )
    def test_refine_path(self, version, path, expected):
        caps = TM1VersionCapabilities(version)
        assert caps.refine_path(path) == expected


# ---------------------------------------------------------------------------
# Buffered file classes
# ---------------------------------------------------------------------------


class TestBufferedFileClasses:
    def test_triad_implemented_on_base(self):
        for m in ["_initiate_upload", "_upload_chunk", "_fetch_range"]:
            assert hasattr(TM1BufferedFile, m), m

    def test_v11_and_v12_implement_triad(self):
        for cls in (TM1FileV11, TM1FileV12):
            for m in ["_initiate_upload", "_upload_chunk", "_fetch_range"]:
                assert hasattr(cls, m), (cls.__name__, m)

    def test_v12_has_mpu_extension_points(self):
        """TM1FileV12 reserves MPU streaming stubs for future enhancement."""
        for m in ["_initiate_mpu", "_upload_part", "_complete_mpu"]:
            assert hasattr(TM1FileV12, m), m


# ---------------------------------------------------------------------------
# Filesystem behaviour: shared across v11 and v12
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("version", ["11.4.0", "12.0.0"])
def test_keystone_methods_exist(version):
    fs, _, _, _ = _make_mock_tm1(version)
    for m in ["ls", "info", "_open", "_rm", "cp_file", "mkdir", "makedirs", "search"]:
        assert hasattr(fs, m), m


@pytest.mark.parametrize("version", ["11.4.0", "12.0.0"])
def test_ls_detail_false_returns_full_paths(version):
    fs, _, names, _ = _make_mock_tm1(version)
    paths = fs.ls("/", detail=False)
    assert paths == ["/alpha.csv", "/beta.csv", "/gamma.json"]


@pytest.mark.parametrize("version", ["11.4.0", "12.0.0"])
def test_ls_detail_true_returns_dicts_with_required_keys(version):
    fs, _, _, _ = _make_mock_tm1(version)
    entries = fs.ls("/", detail=True)
    assert len(entries) == 3
    for entry in entries:
        assert {"name", "size", "type"}.issubset(entry.keys())
        assert entry["type"] == "file"
        # ls returns size=None to avoid an N+1 fetch storm
        assert entry["size"] is None


@pytest.mark.parametrize("version", ["11.4.0", "12.0.0"])
def test_inherited_exists(version):
    fs, _, _, _ = _make_mock_tm1(version)
    assert fs.exists("/alpha.csv") is True
    assert fs.exists("/nope.csv") is False


@pytest.mark.parametrize("version", ["11.4.0", "12.0.0"])
def test_info_fetches_real_size(version):
    fs, _, _, _ = _make_mock_tm1(version)
    info = fs.info("/alpha.csv")
    assert info["size"] == len(b"hello alpha")
    assert info["type"] == "file"
    assert info["name"] == "/alpha.csv"


@pytest.mark.parametrize("version", ["11.4.0", "12.0.0"])
def test_info_root_is_directory(version):
    fs, _, _, _ = _make_mock_tm1(version)
    info = fs.info("/")
    assert info["type"] == "directory"
    assert info["size"] == 0


@pytest.mark.parametrize("version", ["11.4.0", "12.0.0"])
def test_info_missing_raises_file_not_found(version):
    fs, _, _, _ = _make_mock_tm1(version)
    with pytest.raises(FileNotFoundError):
        fs.info("/missing.csv")


@pytest.mark.parametrize("version", ["11.4.0", "12.0.0"])
def test_inherited_isfile_and_size(version):
    fs, _, _, _ = _make_mock_tm1(version)
    assert fs.isfile("/alpha.csv") is True
    assert fs.size("/alpha.csv") == len(b"hello alpha")


@pytest.mark.parametrize("version", ["11.4.0", "12.0.0"])
def test_inherited_find_recurses(version):
    fs, _, _, _ = _make_mock_tm1(version)
    found = fs.find("/")
    assert "/alpha.csv" in found
    assert "/beta.csv" in found
    assert "/gamma.json" in found


@pytest.mark.parametrize("version", ["11.4.0", "12.0.0"])
def test_inherited_glob(version):
    fs, _, _, _ = _make_mock_tm1(version)
    matches = fs.glob("/alpha*")
    assert any("alpha.csv" in m for m in matches)


@pytest.mark.parametrize("version", ["11.4.0", "12.0.0"])
def test_open_read(version):
    fs, _, _, _ = _make_mock_tm1(version)
    with fs.open("/alpha.csv", "rb") as f:
        assert f.read() == b"hello alpha"


@pytest.mark.parametrize("version", ["11.4.0", "12.0.0"])
def test_cat_file_inherited(version):
    fs, _, _, _ = _make_mock_tm1(version)
    assert fs.cat_file("/alpha.csv") == b"hello alpha"


@pytest.mark.parametrize("version", ["11.4.0", "12.0.0"])
def test_open_read_missing_raises(version):
    fs, _, _, _ = _make_mock_tm1(version)
    with pytest.raises(FileNotFoundError):
        fs.open("/missing.csv", "rb")


@pytest.mark.parametrize("version", ["11.4.0", "12.0.0"])
def test_open_unsupported_mode_raises(version):
    fs, _, _, _ = _make_mock_tm1(version)
    with pytest.raises(ValueError, match="Unsupported mode"):
        fs.open("/alpha.csv", "invalid")


@pytest.mark.parametrize("version", ["11.4.0", "12.0.0"])
def test_write_back_via_buffered_file(version):
    fs, tm1, _, _ = _make_mock_tm1(version)
    with fs.open("/new.txt", "wb") as f:
        f.write(b"new content")
    # path sent to TM1py respects version refinement
    expected_path = "new.txt" if version == "11.4.0" else "/new.txt"
    tm1.files.update_or_create.assert_called_once_with(expected_path, b"new content")


@pytest.mark.parametrize("version", ["11.4.0", "12.0.0"])
def test_cp_file_reads_and_reuploads(version):
    fs, tm1, _, _ = _make_mock_tm1(version)
    fs.cp_file("/alpha.csv", "/alpha_copy.csv")
    expected_dst = "alpha_copy.csv" if version == "11.4.0" else "/alpha_copy.csv"
    tm1.files.update_or_create.assert_called_with(expected_dst, b"hello alpha")


@pytest.mark.parametrize("version", ["11.4.0", "12.0.0"])
def test_rm_dispatches_to_delete(version):
    fs, tm1, _, _ = _make_mock_tm1(version)
    fs.rm("/alpha.csv")
    expected_path = "alpha.csv" if version == "11.4.0" else "/alpha.csv"
    tm1.files.delete.assert_called_once_with(expected_path)


@pytest.mark.parametrize("version", ["11.4.0", "12.0.0"])
def test_search_uses_tm1_name_search(version):
    fs, tm1, _, _ = _make_mock_tm1(version)
    tm1.files.search_string_in_name.return_value = ["alpha.csv"]
    result = fs.search("alpha", path="/")
    assert result == ["alpha.csv"]
    tm1.files.search_string_in_name.assert_called_once()


def test_search_requires_at_least_one_term():
    fs, _, _, _ = _make_mock_tm1("12.0.0")
    with pytest.raises(ValueError, match="At least one name_contains"):
        fs.search()


# ---------------------------------------------------------------------------
# Version-specific behaviour
# ---------------------------------------------------------------------------


class TestV11Specific:
    def test_dispatches_v11_file_class(self, fs_v11):
        fs, _, _, _ = fs_v11
        assert fs._caps.buffered_file_cls() is TM1FileV11

    def test_mkdir_is_noop(self, fs_v11):
        fs, tm1, _, _ = fs_v11
        fs.mkdir("/somefolder")
        tm1.files.create_folder.assert_not_called()

    def test_makedirs_is_noop(self, fs_v11):
        fs, tm1, _, _ = fs_v11
        fs.makedirs("/a/b/c")
        tm1.files.create_folder.assert_not_called()


class TestV12Specific:
    def test_dispatches_v12_file_class(self, fs_v12):
        fs, _, _, _ = fs_v12
        assert fs._caps.buffered_file_cls() is TM1FileV12

    def test_mkdir_calls_create_folder(self, fs_v12):
        fs, tm1, _, _ = fs_v12
        tm1.files.exists.return_value = False
        fs.mkdir("/somefolder")
        tm1.files.create_folder.assert_called_once_with("somefolder")

    def test_makedirs_creates_recursively(self, fs_v12):
        fs, tm1, _, _ = fs_v12
        tm1.files.exists.return_value = False
        fs.makedirs("/a/b/c")
        tm1.files.create_folder.assert_called_once_with("a/b/c")


# ---------------------------------------------------------------------------
# Path normalisation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("", "/"),
        ("/", "/"),
        ("//", "/"),
        ("myfile.txt", "/myfile.txt"),
        ("/myfile.txt", "/myfile.txt"),
        ("//myfile.txt", "/myfile.txt"),
        ("tm1://tm1_default@/", "/"),
        ("tm1://tm1_default@/foo/bar", "/foo/bar"),
        ("folder/", "/folder/"),
    ],
)
def test_normalize_path(raw, expected):
    assert _normalize_path(raw) == expected
