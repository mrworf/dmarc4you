#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
E2E_DIR="${ROOT_DIR}/.tmp/e2e"
ENV_FILE="${E2E_DIR}/e2e.env"
SUMMARY_FILE="${E2E_DIR}/seed-summary.json"
BACKEND_LOG="${E2E_DIR}/backend.log"
FRONTEND_LOG="${E2E_DIR}/frontend.log"
CONFIG_PATH="${ROOT_DIR}/config.e2e.yaml"
PLAYWRIGHT_ARGS=("$@")

mkdir -p "${E2E_DIR}"

if [[ -x "${ROOT_DIR}/.venv/bin/python" ]]; then
  PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"
elif [[ -x "${ROOT_DIR}/venv/bin/python" ]]; then
  PYTHON_BIN="${ROOT_DIR}/venv/bin/python"
else
  PYTHON_BIN="python3"
fi

cleanup() {
  local exit_code=$?
  if [[ -n "${BACKEND_PID:-}" ]]; then
    kill "${BACKEND_PID}" >/dev/null 2>&1 || true
    wait "${BACKEND_PID}" >/dev/null 2>&1 || true
  fi
  if [[ -n "${FRONTEND_PID:-}" ]]; then
    kill "${FRONTEND_PID}" >/dev/null 2>&1 || true
    wait "${FRONTEND_PID}" >/dev/null 2>&1 || true
  fi
  "${PYTHON_BIN}" -m cli seed-e2e "${CONFIG_PATH}" --cleanup --env-file "${ENV_FILE}" >/dev/null 2>&1 || true
  exit "${exit_code}"
}

trap cleanup EXIT

cd "${ROOT_DIR}"
"${PYTHON_BIN}" -m cli seed-e2e "${CONFIG_PATH}" --env-file "${ENV_FILE}" --summary-file "${SUMMARY_FILE}"

set -a
# shellcheck disable=SC1090
source "${ENV_FILE}"
set +a

export DMARC_CONFIG="${CONFIG_PATH}"
export DMARC_E2E_BASE_URL="${DMARC_E2E_BASE_URL:-http://127.0.0.1:3001}"
export DMARC_E2E_API_BASE_URL="${DMARC_E2E_API_BASE_URL:-http://127.0.0.1:8001}"
export DMARC_E2E_USE_EXISTING_FRONTEND=1
FRONTEND_PORT="${DMARC_E2E_BASE_URL##*:}"

"${PYTHON_BIN}" -m backend.main >"${BACKEND_LOG}" 2>&1 &
BACKEND_PID=$!

(
  cd "${ROOT_DIR}/frontend"
  npm run dev -- --hostname 127.0.0.1 --port "${FRONTEND_PORT}" >"${FRONTEND_LOG}" 2>&1
) &
FRONTEND_PID=$!

"${PYTHON_BIN}" -c 'import sys,time,urllib.request; url=sys.argv[1]; deadline=time.time()+120
while time.time()<deadline:
    try:
        with urllib.request.urlopen(url, timeout=2) as response:
            if response.status < 500:
                raise SystemExit(0)
    except Exception:
        time.sleep(1)
raise SystemExit(1)' "${DMARC_E2E_API_BASE_URL}/api/v1/health/ready"

"${PYTHON_BIN}" -c 'import sys,time,urllib.request; url=sys.argv[1]; deadline=time.time()+180
while time.time()<deadline:
    try:
        with urllib.request.urlopen(url, timeout=2) as response:
            if response.status < 500:
                raise SystemExit(0)
    except Exception:
        time.sleep(1)
raise SystemExit(1)' "${DMARC_E2E_BASE_URL}/login"

cd "${ROOT_DIR}/frontend"
npx playwright test "${PLAYWRIGHT_ARGS[@]}"
