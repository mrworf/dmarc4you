"""Archive storage protocol definition."""

from typing import Protocol


class ArchiveStorage(Protocol):
    """Protocol for raw artifact storage backends."""

    def store(self, domain: str, report_id: str, data: bytes) -> str:
        """
        Store raw report data for a domain.
        
        Args:
            domain: The domain name (e.g. "example.com")
            report_id: Unique report identifier
            data: Raw report bytes
            
        Returns:
            Storage path or identifier for the stored artifact
        """
        ...

    def count(self, domain: str) -> int:
        """
        Count stored artifacts for a domain.
        
        Args:
            domain: The domain name
            
        Returns:
            Number of stored artifacts for this domain
        """
        ...

    def list(self, domain: str) -> list[str]:
        """
        List artifact IDs for a domain.
        
        Args:
            domain: The domain name
            
        Returns:
            List of artifact IDs (report IDs) stored for this domain
        """
        ...

    def retrieve(self, domain: str, artifact_id: str) -> bytes | None:
        """
        Retrieve raw artifact data.
        
        Args:
            domain: The domain name
            artifact_id: The artifact/report ID
            
        Returns:
            Raw bytes if found, None otherwise
        """
        ...
