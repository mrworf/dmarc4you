"""Optional Docker-backed smoke coverage for endpoint and port wiring."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest


@pytest.mark.skipif(os.environ.get("DMARC_RUN_DOCKER_SMOKE") != "1", reason="docker smoke is local-gated")
def test_docker_endpoint_smoke() -> None:
    subprocess.run(["bash", str(Path("scripts/run_docker_endpoint_smoke.sh"))], check=True)
