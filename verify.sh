#!/usr/bin/env bash
set -euo pipefail

API_BASE_URL="${API_BASE_URL:-http://localhost:8000}"
PDF_FILE="${PDF_FILE:-test_resume.pdf}"
POLL_INTERVAL=3
TIMEOUT_SECONDS=60

command -v curl >/dev/null 2>&1 || {
  echo "FAIL: curl is required"
  exit 1
}

PYTHON_CMD=()
if command -v python3 >/dev/null 2>&1 && python3 -c 'import sys,json' >/dev/null 2>&1; then
  PYTHON_CMD=(python3)
elif command -v python >/dev/null 2>&1 && python -c 'import sys,json' >/dev/null 2>&1; then
  PYTHON_CMD=(python)
elif command -v py >/dev/null 2>&1 && py -3.12 -c 'import sys,json' >/dev/null 2>&1; then
  PYTHON_CMD=(py -3.12)
elif [[ -n "${LOCALAPPDATA:-}" ]]; then
  python312_path="${LOCALAPPDATA//\\//}/Programs/Python/Python312/python.exe"
  if [[ -x "$python312_path" ]]; then
    PYTHON_CMD=("$python312_path")
  fi
fi

if [[ "${#PYTHON_CMD[@]}" -eq 0 ]]; then
  echo "FAIL: python is required"
  exit 1
fi

if ! "${PYTHON_CMD[@]}" -c 'import sys,json' >/dev/null 2>&1; then
  echo "FAIL: python is required"
  exit 1
fi

if [[ ! -f "$PDF_FILE" ]]; then
  echo "FAIL: missing test PDF $PDF_FILE"
  exit 1
fi

if ! health_code="$(curl -sS -o /dev/null -w "%{http_code}" "$API_BASE_URL/health")"; then
  echo "FAIL: API health check request failed"
  exit 1
fi

if [[ "$health_code" != "200" ]]; then
  echo "FAIL: API health check returned HTTP $health_code"
  exit 1
fi

if ! upload_response="$(curl -sS -X POST "$API_BASE_URL/parse" -F "file=@${PDF_FILE}")"; then
  echo "FAIL: upload request failed"
  exit 1
fi

if ! task_id="$("${PYTHON_CMD[@]}" -c 'import sys,json; print(json.load(sys.stdin)["task_id"])' <<<"$upload_response")"; then
  echo "FAIL: parse response was not valid JSON"
  echo "$upload_response"
  exit 1
fi

if [[ -z "$task_id" ]]; then
  echo "FAIL: missing task_id in parse response"
  echo "$upload_response"
  exit 1
fi

result_response=""
status=""
elapsed=0

while (( elapsed < TIMEOUT_SECONDS )); do
  if ! result_response="$(curl -sS "$API_BASE_URL/results/$task_id")"; then
    echo "FAIL: result request failed"
    exit 1
  fi

  if ! status="$("${PYTHON_CMD[@]}" -c 'import sys,json; print(json.load(sys.stdin).get("status", ""))' <<<"$result_response")"; then
    echo "FAIL: result response was not valid JSON"
    echo "$result_response"
    exit 1
  fi

  if [[ "$status" == "done" || "$status" == "failed" ]]; then
    break
  fi

  sleep "$POLL_INTERVAL"
  elapsed=$((elapsed + POLL_INTERVAL))
done

if [[ "$status" == "failed" ]]; then
  echo "FAIL: task failed"
  exit 1
fi

if [[ "$status" != "done" ]]; then
  echo "FAIL: timeout waiting for result"
  exit 1
fi

for field in name email skills experience education; do
  if ! FIELD="$field" "${PYTHON_CMD[@]}" -c 'import os,sys,json; sys.exit(0 if os.environ["FIELD"] in json.load(sys.stdin) else 1)' <<<"$result_response"; then
    echo "FAIL: missing field $field"
    exit 1
  fi
done

echo "OK"
