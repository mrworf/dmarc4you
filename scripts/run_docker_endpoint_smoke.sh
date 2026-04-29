#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP_DIR="${ROOT_DIR}/.tmp/docker-endpoint-smoke"
ENV_FILE="${TMP_DIR}/compose.env"
COMPOSE_PROJECT="dmarc4you-smoke-${RANDOM}"

WEB_PORT="${DMARC_DOCKER_SMOKE_WEB_PORT:-33111}"
API_PORT="${DMARC_DOCKER_SMOKE_API_PORT:-38111}"
WEB_INTERNAL_PORT="${DMARC_DOCKER_SMOKE_WEB_INTERNAL_PORT:-3111}"
API_INTERNAL_PORT="${DMARC_DOCKER_SMOKE_API_INTERNAL_PORT:-8111}"

mkdir -p "${TMP_DIR}"

cleanup() {
  docker compose \
    --project-name "${COMPOSE_PROJECT}" \
    --env-file "${ENV_FILE}" \
    -f "${ROOT_DIR}/compose.yaml" \
    -f "${ROOT_DIR}/compose.override.localbuild.yaml" \
    down -v --remove-orphans >/dev/null 2>&1 || true
}

trap cleanup EXIT

cat >"${ENV_FILE}" <<EOF
DMARC_WEB_PORT=${WEB_PORT}
DMARC_API_PORT=${API_PORT}
DMARC_WEB_INTERNAL_PORT=${WEB_INTERNAL_PORT}
DMARC_SERVER_PORT=${API_INTERNAL_PORT}
DMARC_SESSION_SECRET=docker-smoke-secret
DMARC_FRONTEND_PUBLIC_ORIGIN=http://127.0.0.1:${WEB_PORT}
DMARC_CORS_ALLOWED_ORIGINS=http://127.0.0.1:${WEB_PORT}
DMARC_API_PUBLIC_URL=http://127.0.0.1:${API_PORT}
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:${API_PORT}
NEXT_PUBLIC_CSRF_COOKIE_NAME=dmarc_csrf
NEXT_PUBLIC_REQUEST_ID_HEADER_NAME=X-Request-ID
DMARC_ARCHIVE_STORAGE_PATH=/app/archive
DMARC_GEOIP_PROVIDER=none
LOCAL_WEB_BUILD_NEXT_PUBLIC_API_BASE_URL=http://build-time.invalid:65535
EOF

docker compose \
  --project-name "${COMPOSE_PROJECT}" \
  --env-file "${ENV_FILE}" \
  -f "${ROOT_DIR}/compose.yaml" \
  -f "${ROOT_DIR}/compose.override.localbuild.yaml" \
  up --build -d

BOOTSTRAP_PASSWORD="$(python3 - <<'PY' "${COMPOSE_PROJECT}" "${ENV_FILE}" "${ROOT_DIR}" "${WEB_PORT}" "${API_PORT}"
import json
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

project, env_file, root_dir, web_port, api_port = sys.argv[1:]
compose_args = [
    "docker",
    "compose",
    "--project-name",
    project,
    "--env-file",
    env_file,
    "-f",
    str(Path(root_dir) / "compose.yaml"),
    "-f",
    str(Path(root_dir) / "compose.override.localbuild.yaml"),
]

deadline = time.time() + 300
while time.time() < deadline:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{api_port}/api/v1/health/ready", timeout=3) as response:
            payload = json.load(response)
        if payload.get("status") == "ok":
            break
    except Exception:
        time.sleep(2)
else:
    raise SystemExit("backend readiness endpoint did not become healthy")

deadline = time.time() + 300
frontend_payload = None
while time.time() < deadline:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{web_port}/api/ready", timeout=3) as response:
            frontend_payload = json.load(response)
        if frontend_payload.get("status") == "ok":
            break
    except Exception:
        time.sleep(2)
else:
    raise SystemExit("frontend readiness endpoint did not become healthy")

expected_api_url = f"http://127.0.0.1:{api_port}"
if frontend_payload["backend"]["apiBaseUrl"] != expected_api_url:
    raise SystemExit(
        f"frontend reported backend {frontend_payload['backend']['apiBaseUrl']!r}, expected {expected_api_url!r}"
    )

ps_output = subprocess.check_output(compose_args + ["ps"], text=True)
if "healthy" not in ps_output:
    raise SystemExit(f"compose services did not report healthy status:\n{ps_output}")

pattern = re.compile(r"Bootstrap admin password .*: (\S+)")
deadline = time.time() + 120
while time.time() < deadline:
    logs = subprocess.check_output(compose_args + ["logs", "api"], text=True)
    match = pattern.search(logs)
    if match:
        print(match.group(1))
        raise SystemExit(0)
    time.sleep(2)

raise SystemExit("could not extract bootstrap password")
PY
)"

(
  cd "${ROOT_DIR}/frontend"
  DMARC_E2E_BASE_URL="http://127.0.0.1:${WEB_PORT}" \
  DMARC_E2E_USE_EXISTING_FRONTEND=1 \
  DMARC_E2E_SUPERADMIN_USERNAME="admin" \
  DMARC_E2E_SUPERADMIN_PASSWORD="${BOOTSTRAP_PASSWORD}" \
  npx playwright test e2e/docker-compose.spec.ts
)
