"""Unit tests for FilesystemArchiveStorage."""

import tempfile
from pathlib import Path

import pytest

from backend.archive.filesystem import FilesystemArchiveStorage


@pytest.fixture
def temp_archive_dir():
    """Create a temporary directory for archive storage."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


class TestFilesystemArchiveStorage:
    """Tests for FilesystemArchiveStorage."""

    def test_store_creates_domain_directory(self, temp_archive_dir: str):
        """store() creates the domain subdirectory if it doesn't exist."""
        storage = FilesystemArchiveStorage(temp_archive_dir)
        storage.store("example.com", "report-123", b"<xml>data</xml>")

        domain_dir = Path(temp_archive_dir) / "example.com"
        assert domain_dir.is_dir()

    def test_store_writes_raw_file(self, temp_archive_dir: str):
        """store() writes the data to a .raw file."""
        storage = FilesystemArchiveStorage(temp_archive_dir)
        data = b"<feedback><report_metadata>...</report_metadata></feedback>"
        storage.store("example.com", "report-456", data)

        file_path = Path(temp_archive_dir) / "example.com" / "report-456.raw"
        assert file_path.is_file()
        assert file_path.read_bytes() == data

    def test_store_returns_path(self, temp_archive_dir: str):
        """store() returns the path to the stored file."""
        storage = FilesystemArchiveStorage(temp_archive_dir)
        path = storage.store("test.org", "rpt-789", b"data")

        assert path.endswith(".raw")
        assert "test.org" in path

    def test_store_sanitizes_domain_name(self, temp_archive_dir: str):
        """store() sanitizes domain names for safe filesystem paths."""
        storage = FilesystemArchiveStorage(temp_archive_dir)
        storage.store("sub.domain.example.com", "report-1", b"data")

        domain_dir = Path(temp_archive_dir) / "sub.domain.example.com"
        assert domain_dir.is_dir()

    def test_store_sanitizes_report_id(self, temp_archive_dir: str):
        """store() sanitizes report IDs with special characters."""
        storage = FilesystemArchiveStorage(temp_archive_dir)
        storage.store("example.com", "google.com!example.com!1709251200!1709337600", b"data")

        domain_dir = Path(temp_archive_dir) / "example.com"
        files = list(domain_dir.glob("*.raw"))
        assert len(files) == 1

    def test_store_handles_empty_report_id(self, temp_archive_dir: str):
        """store() uses hash fallback for empty/invalid report IDs."""
        storage = FilesystemArchiveStorage(temp_archive_dir)
        storage.store("example.com", "!!!", b"data")

        domain_dir = Path(temp_archive_dir) / "example.com"
        files = list(domain_dir.glob("*.raw"))
        assert len(files) == 1

    def test_count_empty_directory(self, temp_archive_dir: str):
        """count() returns 0 for non-existent domain directory."""
        storage = FilesystemArchiveStorage(temp_archive_dir)
        assert storage.count("nonexistent.com") == 0

    def test_count_returns_artifact_count(self, temp_archive_dir: str):
        """count() returns the number of .raw files in domain directory."""
        storage = FilesystemArchiveStorage(temp_archive_dir)
        storage.store("example.com", "report-1", b"data1")
        storage.store("example.com", "report-2", b"data2")
        storage.store("example.com", "report-3", b"data3")

        assert storage.count("example.com") == 3

    def test_count_ignores_other_files(self, temp_archive_dir: str):
        """count() only counts .raw files, not other files."""
        storage = FilesystemArchiveStorage(temp_archive_dir)
        storage.store("example.com", "report-1", b"data")

        other_file = Path(temp_archive_dir) / "example.com" / "metadata.json"
        other_file.write_text("{}")

        assert storage.count("example.com") == 1

    def test_count_per_domain_isolation(self, temp_archive_dir: str):
        """count() returns count only for the specified domain."""
        storage = FilesystemArchiveStorage(temp_archive_dir)
        storage.store("domain-a.com", "report-1", b"data")
        storage.store("domain-a.com", "report-2", b"data")
        storage.store("domain-b.com", "report-1", b"data")

        assert storage.count("domain-a.com") == 2
        assert storage.count("domain-b.com") == 1

    def test_store_overwrites_existing_file(self, temp_archive_dir: str):
        """store() overwrites if the same report_id is stored twice."""
        storage = FilesystemArchiveStorage(temp_archive_dir)
        storage.store("example.com", "report-1", b"original")
        storage.store("example.com", "report-1", b"updated")

        file_path = Path(temp_archive_dir) / "example.com" / "report-1.raw"
        assert file_path.read_bytes() == b"updated"
        assert storage.count("example.com") == 1

    def test_list_empty_directory(self, temp_archive_dir: str):
        """list() returns empty list for non-existent domain directory."""
        storage = FilesystemArchiveStorage(temp_archive_dir)
        assert storage.list("nonexistent.com") == []

    def test_list_returns_artifact_ids(self, temp_archive_dir: str):
        """list() returns artifact IDs (filenames without .raw extension)."""
        storage = FilesystemArchiveStorage(temp_archive_dir)
        storage.store("example.com", "report-1", b"data1")
        storage.store("example.com", "report-2", b"data2")
        storage.store("example.com", "report-3", b"data3")

        result = storage.list("example.com")
        assert sorted(result) == ["report-1", "report-2", "report-3"]

    def test_list_returns_sorted(self, temp_archive_dir: str):
        """list() returns artifact IDs in sorted order."""
        storage = FilesystemArchiveStorage(temp_archive_dir)
        storage.store("example.com", "zebra", b"data")
        storage.store("example.com", "alpha", b"data")
        storage.store("example.com", "middle", b"data")

        result = storage.list("example.com")
        assert result == ["alpha", "middle", "zebra"]

    def test_list_ignores_non_raw_files(self, temp_archive_dir: str):
        """list() only returns .raw files, not other files."""
        storage = FilesystemArchiveStorage(temp_archive_dir)
        storage.store("example.com", "report-1", b"data")

        other_file = Path(temp_archive_dir) / "example.com" / "metadata.json"
        other_file.write_text("{}")

        result = storage.list("example.com")
        assert result == ["report-1"]

    def test_list_per_domain_isolation(self, temp_archive_dir: str):
        """list() returns artifacts only for the specified domain."""
        storage = FilesystemArchiveStorage(temp_archive_dir)
        storage.store("domain-a.com", "report-a1", b"data")
        storage.store("domain-a.com", "report-a2", b"data")
        storage.store("domain-b.com", "report-b1", b"data")

        assert storage.list("domain-a.com") == ["report-a1", "report-a2"]
        assert storage.list("domain-b.com") == ["report-b1"]

    def test_retrieve_returns_bytes(self, temp_archive_dir: str):
        """retrieve() returns the stored bytes."""
        storage = FilesystemArchiveStorage(temp_archive_dir)
        data = b"<xml>report data</xml>"
        storage.store("example.com", "report-1", data)

        result = storage.retrieve("example.com", "report-1")
        assert result == data

    def test_retrieve_nonexistent_domain_returns_none(self, temp_archive_dir: str):
        """retrieve() returns None for non-existent domain."""
        storage = FilesystemArchiveStorage(temp_archive_dir)
        assert storage.retrieve("nonexistent.com", "report-1") is None

    def test_retrieve_nonexistent_artifact_returns_none(self, temp_archive_dir: str):
        """retrieve() returns None for non-existent artifact."""
        storage = FilesystemArchiveStorage(temp_archive_dir)
        storage.store("example.com", "report-1", b"data")

        assert storage.retrieve("example.com", "nonexistent") is None

    def test_retrieve_empty_artifact_id_returns_none(self, temp_archive_dir: str):
        """retrieve() returns None for empty/invalid artifact ID."""
        storage = FilesystemArchiveStorage(temp_archive_dir)
        storage.store("example.com", "report-1", b"data")

        assert storage.retrieve("example.com", "") is None
        assert storage.retrieve("example.com", "!!!") is None


class TestSafeName:
    """Tests for the _safe_name helper."""

    def test_preserves_alphanumeric(self):
        """_safe_name preserves alphanumeric characters."""
        assert FilesystemArchiveStorage._safe_name("example123") == "example123"

    def test_preserves_dots_and_hyphens(self):
        """_safe_name preserves dots and hyphens."""
        assert FilesystemArchiveStorage._safe_name("sub.domain-test.com") == "sub.domain-test.com"

    def test_replaces_special_chars(self):
        """_safe_name replaces special characters with underscores."""
        assert FilesystemArchiveStorage._safe_name("a/b:c*d") == "a_b_c_d"

    def test_strips_leading_trailing_special(self):
        """_safe_name strips leading/trailing dots and underscores."""
        assert FilesystemArchiveStorage._safe_name("...test___") == "test"
        assert FilesystemArchiveStorage._safe_name("_.name._") == "name"
