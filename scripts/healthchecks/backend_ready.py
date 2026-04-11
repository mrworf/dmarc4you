#!/usr/bin/env python3
"""Backend readiness probe for container health checks."""

from __future__ import annotations

import json
import sys
import urllib.request


def main() -> int:
    try:
        response = urllib.request.urlopen("http://127.0.0.1:8000/api/v1/health/ready", timeout=5)
        with response:
            payload = json.load(response)
    except Exception:
        return 1
    return 0 if payload.get("status") == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
