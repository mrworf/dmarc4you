"""Shared ingest API client for CLI-based DMARC report submission."""

from __future__ import annotations

import base64
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable

TERMINAL_JOB_STATES = frozenset({"completed", "completed_with_warnings"})
SUCCESSFUL_ITEM_STATUSES = frozenset({"accepted", "duplicate"})


class IngestApiError(RuntimeError):
    """Raised when the ingest API request or response is invalid."""


class IngestJobTimeoutError(IngestApiError):
    """Raised when a queued ingest job does not reach a terminal state in time."""


@dataclass
class IngestApiClient:
    """Small HTTP client for report submission and ingest-job polling."""

    api_key: str
    base_url: str
    request_timeout: float = 30.0

    def submit_reports(self, source: str, reports: list[dict[str, str]]) -> str:
        """Submit one or more pre-encoded reports and return the created job id."""
        payload = {"source": source, "reports": reports}
        response = self._request_json("/api/v1/reports/ingest", method="POST", payload=payload)
        job_id = response.get("job_id")
        if not job_id:
            raise IngestApiError("Ingest response missing job_id")
        return str(job_id)

    def submit_report_bytes(
        self,
        *,
        source: str,
        content: bytes,
        content_type: str,
        content_encoding: str = "",
        content_transfer_encoding: str = "base64",
    ) -> str:
        """Submit one raw payload as a single ingest report and return the job id."""
        encoded = base64.b64encode(content).decode("ascii")
        return self.submit_reports(
            source,
            [
                {
                    "content_type": content_type,
                    "content_encoding": content_encoding,
                    "content_transfer_encoding": content_transfer_encoding,
                    "content": encoded,
                }
            ],
        )

    def get_job_detail(self, job_id: str) -> dict[str, Any]:
        """Fetch ingest job detail for one previously submitted job."""
        quoted_job_id = urllib.parse.quote(job_id, safe="")
        response = self._request_json(f"/api/v1/ingest-jobs/{quoted_job_id}", method="GET")
        if not isinstance(response, dict):
            raise IngestApiError("Unexpected job detail response")
        return response

    def wait_for_job_terminal(
        self,
        job_id: str,
        *,
        timeout_seconds: float,
        poll_interval_seconds: float = 2.0,
        sleep_fn: Callable[[float], None] = time.sleep,
    ) -> dict[str, Any]:
        """Poll a job until it reaches a terminal state or timeout expires."""
        deadline = time.monotonic() + max(timeout_seconds, 0.0)
        while True:
            job = self.get_job_detail(job_id)
            if is_terminal_job(job):
                return job
            if time.monotonic() >= deadline:
                raise IngestJobTimeoutError(f"Timed out waiting for ingest job {job_id}")
            sleep_fn(poll_interval_seconds)

    def _request_json(
        self,
        path: str,
        *,
        method: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = self.base_url.rstrip("/") + path
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(
            url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=self.request_timeout) as response:
                raw_body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            response_body = ""
            try:
                response_body = exc.read().decode("utf-8", errors="replace").strip()
            except Exception:
                response_body = ""
            detail = f"{exc.code} {exc.reason}"
            if response_body:
                detail = f"{detail} {response_body}"
            raise IngestApiError(detail) from exc
        except urllib.error.URLError as exc:
            raise IngestApiError(f"Connection error: {exc.reason}") from exc
        except Exception as exc:
            raise IngestApiError(str(exc)) from exc

        try:
            parsed = json.loads(raw_body)
        except json.JSONDecodeError as exc:
            raise IngestApiError("Response was not valid JSON") from exc
        if not isinstance(parsed, dict):
            raise IngestApiError("Response JSON was not an object")
        return parsed


def is_terminal_job(job: dict[str, Any]) -> bool:
    """Return whether the ingest job reached one of the backend terminal states."""
    return str(job.get("state") or "") in TERMINAL_JOB_STATES


def is_successful_job(job: dict[str, Any]) -> bool:
    """Return whether every job item completed successfully for the uploaded message."""
    if not is_terminal_job(job):
        return False
    items = job.get("items")
    if not isinstance(items, list) or not items:
        return False
    statuses = [str(item.get("status") or "") for item in items if isinstance(item, dict)]
    if not statuses:
        return False
    return all(status in SUCCESSFUL_ITEM_STATUSES for status in statuses)
