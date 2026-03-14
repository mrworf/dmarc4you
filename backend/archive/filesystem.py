"""Filesystem-based archive storage implementation."""

import hashlib
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class FilesystemArchiveStorage:
    """Store raw artifacts on the local filesystem."""

    def __init__(self, base_path: str | Path):
        """
        Initialize filesystem archive storage.
        
        Args:
            base_path: Root directory for artifact storage
        """
        self._base_path = Path(base_path)

    def store(self, domain: str, report_id: str, data: bytes) -> str:
        """
        Store raw report data in {base_path}/{domain}/{safe_report_id}.raw.
        
        The report_id is sanitized to create a safe filename. If the sanitized
        name would be empty, a hash of the original report_id is used.
        """
        domain_dir = self._base_path / self._safe_name(domain)
        domain_dir.mkdir(parents=True, exist_ok=True)

        safe_id = self._safe_name(report_id)
        if not safe_id:
            safe_id = hashlib.sha256(report_id.encode()).hexdigest()[:16]

        file_path = domain_dir / f"{safe_id}.raw"
        file_path.write_bytes(data)
        logger.debug("Archived artifact: %s", file_path)
        return str(file_path)

    def count(self, domain: str) -> int:
        """Count .raw files in the domain subdirectory."""
        domain_dir = self._base_path / self._safe_name(domain)
        if not domain_dir.is_dir():
            return 0
        return sum(1 for f in domain_dir.iterdir() if f.suffix == ".raw" and f.is_file())

    def list(self, domain: str) -> list[str]:
        """List artifact IDs (filenames without .raw extension) for a domain."""
        domain_dir = self._base_path / self._safe_name(domain)
        if not domain_dir.is_dir():
            return []
        return sorted(
            f.stem for f in domain_dir.iterdir() if f.suffix == ".raw" and f.is_file()
        )

    def retrieve(self, domain: str, artifact_id: str) -> bytes | None:
        """Retrieve raw artifact bytes by ID. Returns None if not found."""
        safe_domain = self._safe_name(domain)
        safe_id = self._safe_name(artifact_id)
        if not safe_id:
            return None
        file_path = self._base_path / safe_domain / f"{safe_id}.raw"
        if not file_path.is_file():
            return None
        try:
            return file_path.read_bytes()
        except OSError:
            logger.warning("Failed to read artifact: %s", file_path)
            return None

    @staticmethod
    def _safe_name(name: str) -> str:
        """Convert name to a safe filesystem name, preserving dots and hyphens."""
        safe = "".join(c if c.isalnum() or c in ".-_" else "_" for c in name)
        return safe.strip("._")
