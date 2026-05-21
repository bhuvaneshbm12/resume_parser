#!/usr/bin/env bash
set -uo pipefail

API_BASE_URL="${API_BASE_URL:-http://localhost:8000}"
FRONTEND_BASE_URL="${FRONTEND_BASE_URL:-http://localhost:3000}"
PDF_FILE="${PDF_FILE:-test_resume.pdf}"
POLL_INTERVAL=3
TIMEOUT_SECONDS=90
QUICK=0
PROD=0
CI=0

for arg in "$@"; do
  case "$arg" in
    --quick)
      QUICK=1
      ;;
    --ci)
      CI=1
      ;;
    --prod)
      PROD=1
      API_BASE_URL="https://web-production-9d5d8.up.railway.app"
      FRONTEND_BASE_URL="https://resume-parser-khaki-theta.vercel.app"
      ;;
    *)
      echo "FAIL: unknown argument $arg"
      exit 1
      ;;
  esac
done

BOLD_WHITE="\033[1;37m"
GREEN="\033[0;32m"
RED="\033[0;31m"
YELLOW="\033[0;33m"
RESET="\033[0m"

if (( CI == 1 )); then
  BOLD_WHITE=""
  GREEN=""
  RED=""
  YELLOW=""
  RESET=""
fi

PASS_COUNT=0
FAIL_COUNT=0
CRITICAL_FAILED=0
TMP_FILES=()

cleanup() {
  for file in "${TMP_FILES[@]}"; do
    [[ -n "$file" && -f "$file" ]] && rm -f "$file"
  done
}
trap cleanup EXIT

section() {
  if (( CI == 1 )); then
    return
  fi
  printf "\n${BOLD_WHITE}=== %s ===${RESET}\n" "$1"
}

pass() {
  PASS_COUNT=$((PASS_COUNT + 1))
  printf "${GREEN}PASS${RESET}: %s\n" "$1"
}

fail() {
  FAIL_COUNT=$((FAIL_COUNT + 1))
  CRITICAL_FAILED=1
  printf "${RED}FAIL${RESET}: %s\n" "$1"
}

warning() {
  if (( CI == 1 )); then
    return
  fi
  printf "${YELLOW}WARNING${RESET}: %s\n" "$1"
}

http_code() {
  curl -sS -o /dev/null -w "%{http_code}" "$@"
}

json_value() {
  "${PYTHON_CMD[@]}" -c "$1"
}

make_temp_file() {
  local prefix="$1"
  local suffix="$2"
  local base_dir
  # Convert Git Bash path to a Windows path that MinGW curl can read
  base_dir="$(cmd //c echo %TEMP% 2>/dev/null | tr -d '\r')"
  [[ -z "$base_dir" ]] && base_dir="$PWD"
  mktemp "${base_dir%/}/${prefix}.XXXXXX.${suffix}"
}

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

if [[ "${#PYTHON_CMD[@]}" -eq 0 ]] || ! "${PYTHON_CMD[@]}" -c 'import sys,json' >/dev/null 2>&1; then
  echo "FAIL: python is required"
  exit 1
fi

COMPOSE_CMD=()
if command -v docker-compose >/dev/null 2>&1; then
  COMPOSE_CMD=(docker-compose)
elif command -v docker >/dev/null 2>&1; then
  COMPOSE_CMD=(docker compose)
fi

check_http_status() {
  local label="$1"
  local expected="$2"
  shift 2
  local code

  if ! code="$(http_code "$@")"; then
    fail "$label request failed"
    return 1
  fi

  if [[ "$code" == "$expected" ]]; then
    pass "$label returned HTTP $expected"
    return 0
  fi

  fail "$label returned HTTP $code, expected $expected"
  return 1
}

check_service_up() {
  local service="$1"
  local output

  if [[ "${#COMPOSE_CMD[@]}" -eq 0 ]]; then
    fail "docker compose command is not available"
    return 1
  fi

  if ! output="$("${COMPOSE_CMD[@]}" ps "$service" 2>&1)"; then
    fail "$service status check failed: $output"
    return 1
  fi

  if grep -Eq 'Exit|Restarting' <<<"$output"; then
    fail "$service is not stable: $(tr '\n' ' ' <<<"$output")"
    return 1
  fi

  if grep -q 'Up' <<<"$output"; then
    pass "$service is Up"
    return 0
  fi

  fail "$service is not Up: $(tr '\n' ' ' <<<"$output")"
  return 1
}

section "Checking services"
check_http_status "API health" "200" "$API_BASE_URL/health"
check_http_status "Frontend home" "200" "$FRONTEND_BASE_URL"

if (( QUICK == 0 && PROD == 0 )); then
  for service in api worker redis postgres frontend; do
    check_service_up "$service"
  done
elif (( PROD == 1 )); then
  warning "prod mode: skipping docker compose service status checks"
else
  warning "quick mode: skipping docker compose service status checks"
fi

if (( QUICK == 0 )); then
  section "Testing file validation"

  txt_file="$(make_temp_file "verify-upload" "txt")"
  TMP_FILES+=("$txt_file")
  printf "not a pdf\n" >"$txt_file"
  check_http_status "POST /parse with .txt file" "415" -X POST "$API_BASE_URL/parse" -F "file=@${txt_file};type=text/plain"

  check_http_status "POST /parse with no file" "422" -X POST "$API_BASE_URL/parse"

  large_file="$(make_temp_file "verify-large" "pdf")"
  TMP_FILES+=("$large_file")
  "${PYTHON_CMD[@]}" -c 'import sys; open(sys.argv[1], "wb").write(b"x" * (6 * 1024 * 1024))' "$large_file"
  check_http_status "POST /parse with file over 5MB" "413" -X POST "$API_BASE_URL/parse" -F "file=@${large_file};type=application/pdf"

  check_http_status "GET /results/fake-id-999" "404" "$API_BASE_URL/results/fake-id-999"
else
  warning "quick mode: skipping file validation checks"
fi

section "Testing golden path"

if [[ ! -f "$PDF_FILE" ]]; then
  fail "missing test PDF $PDF_FILE"
else
  upload_response=""
  if upload_response="$(curl -sS -X POST "$API_BASE_URL/parse" -F "file=@${PDF_FILE}")"; then
    pass "POST /parse with $PDF_FILE completed"
  else
    fail "POST /parse with $PDF_FILE failed"
  fi

  task_id=""
  if [[ -n "$upload_response" ]] && task_id="$(json_value 'import sys,json; print(json.load(sys.stdin).get("task_id", ""))' <<<"$upload_response")" && [[ -n "$task_id" ]]; then
    pass "parse response included task_id"
  else
    fail "parse response did not include task_id"
    [[ -n "$upload_response" ]] && echo "$upload_response"
  fi

  result_response=""
  status=""
  elapsed=0

  if [[ -n "$task_id" ]]; then
    while (( elapsed < TIMEOUT_SECONDS )); do
      if ! result_response="$(curl -sS "$API_BASE_URL/results/$task_id")"; then
        fail "GET /results/$task_id failed"
        break
      fi

      if ! status="$(json_value 'import sys,json; print(json.load(sys.stdin).get("status", ""))' <<<"$result_response")"; then
        fail "result response was not valid JSON"
        echo "$result_response"
        break
      fi

      if [[ "$status" == "done" || "$status" == "failed" ]]; then
        break
      fi

      sleep "$POLL_INTERVAL"
      elapsed=$((elapsed + POLL_INTERVAL))
    done

    if [[ "$status" == "done" ]]; then
      pass "task completed with status done"
    elif [[ "$status" == "failed" ]]; then
      fail "task completed with status failed"
    else
      fail "timeout waiting for result after ${TIMEOUT_SECONDS}s"
    fi
  fi

  if [[ "$status" == "done" ]]; then
    for field in name email skills experience education; do
      if FIELD="$field" json_value 'import os,sys,json; data=json.load(sys.stdin); sys.exit(0 if os.environ["FIELD"] in data else 1)' <<<"$result_response"; then
        pass "result includes $field"
      else
        fail "result missing $field"
      fi
    done

    if json_value 'import sys,json; data=json.load(sys.stdin); sys.exit(0 if str(data.get("name", "")).strip() else 1)' <<<"$result_response"; then
      pass "name is not empty"
    else
      fail "name is empty"
    fi

    if json_value 'import sys,json; data=json.load(sys.stdin); skills=data.get("skills"); sys.exit(0 if isinstance(skills, list) and len(skills) > 0 else 1)' <<<"$result_response"; then
      pass "skills is a non-empty array"
    else
      fail "skills is not a non-empty array"
    fi
  fi
fi

if (( QUICK == 0 && PROD == 0 )); then
  section "Checking database"

  if [[ "${#COMPOSE_CMD[@]}" -eq 0 ]]; then
    fail "docker compose command is not available"
  else
    db_count_output="$("${COMPOSE_CMD[@]}" exec -T postgres psql -U postgres -d resumes -tAc 'SELECT COUNT(*) FROM resumes WHERE status='"'"'done'"'"'' 2>&1)"
    db_status=$?

    if [[ "$db_status" -ne 0 ]]; then
      fail "database count query failed: $db_count_output"
    elif [[ "$db_count_output" =~ ^[[:space:]]*[1-9][0-9]*[[:space:]]*$ ]]; then
      pass "database has done resumes count $db_count_output"
    else
      fail "database has no done resumes"
    fi
  fi
elif (( PROD == 1 )); then
  warning "prod mode: skipping database checks"
else
  warning "quick mode: skipping database checks"
fi

if (( QUICK == 0 )); then
  section "Checking logs"

  if [[ "${#COMPOSE_CMD[@]}" -eq 0 ]]; then
    warning "docker compose command is not available; skipping log checks"
  else
    for service in api worker; do
      log_output="$("${COMPOSE_CMD[@]}" logs "$service" 2>&1)"
      log_status=$?
      if [[ "$log_status" -ne 0 ]]; then
        warning "could not read $service logs"
        continue
      fi

      error_count="$(grep -c ERROR <<<"$log_output" || true)"
      if (( error_count > 0 )); then
        warning "$service logs contain $error_count ERROR lines"
      else
        pass "$service logs contain 0 ERROR lines"
      fi
    done
  fi
else
  warning "quick mode: skipping log checks"
fi

section "Summary"
if (( CI == 0 )); then
  printf "${GREEN}PASS${RESET}: %s\n" "$PASS_COUNT"
  printf "${RED}FAIL${RESET}: %s\n" "$FAIL_COUNT"
fi

if (( CRITICAL_FAILED == 0 )); then
  if (( CI == 1 )); then
    echo "OK"
  fi
  exit 0
fi

if (( CI == 1 )); then
  echo "FAIL"
fi
exit 1
