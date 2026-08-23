#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/.env"
COMPOSE_FILE="${SCRIPT_DIR}/docker-compose.base.yml"

fail=0

ok() {
  echo "OK   - $1"
}

warn() {
  echo "WARN - $1"
}

bad() {
  echo "FAIL - $1"
  fail=1
}

echo "=== FANZ DEPLOYMENT PREFLIGHT ==="
echo

echo "--- Host ---"
echo "hostname: $(hostname)"
echo "kernel:   $(uname -sr)"
echo "arch:     $(uname -m)"

echo
echo "--- Docker ---"

if command -v docker >/dev/null 2>&1; then
  ok "docker installed"
  docker --version
else
  bad "docker not installed"
fi

if docker compose version >/dev/null 2>&1; then
  ok "Docker Compose plugin available"
  docker compose version
else
  bad "Docker Compose plugin unavailable"
fi

if docker info >/dev/null 2>&1; then
  ok "current user can access Docker daemon"
else
  bad "current user cannot access Docker daemon"
fi

echo
echo "--- Repository files ---"

for file in \
  "${COMPOSE_FILE}" \
  "${SCRIPT_DIR}/.env.example" \
  "${SCRIPT_DIR}/deploy.sh"
do
  if [ -f "${file}" ]; then
    ok "$(basename "${file}") present"
  else
    bad "${file} missing"
  fi
done

echo
echo "--- Environment ---"

if [ -f "${ENV_FILE}" ]; then
  ok "deploy/.env exists"

  if grep -Eq 'replace-with-|example\.com|smtp\.example\.com' "${ENV_FILE}"; then
    bad "deploy/.env still contains placeholder values"
  else
    ok "no known placeholder values detected"
  fi
else
  warn "deploy/.env does not exist yet"
  echo "     create with: cp deploy/.env.example deploy/.env"
fi

echo
echo "--- Compose validation ---"

if [ -f "${ENV_FILE}" ]; then
  if docker compose \
      --env-file "${ENV_FILE}" \
      -f "${COMPOSE_FILE}" \
      config --quiet; then
    ok "compose configuration valid"
  else
    bad "compose configuration invalid"
  fi
else
  warn "compose validation skipped because deploy/.env is absent"
fi

echo
echo "--- Disk ---"
df -h /

avail_kb="$(df -Pk / | awk 'NR==2 {print $4}')"

if [ "${avail_kb}" -ge 20971520 ]; then
  ok "at least 20 GiB free on root filesystem"
else
  warn "less than 20 GiB free on root filesystem"
fi

echo
echo "--- Network / ports ---"

if docker network inspect fanz-net >/dev/null 2>&1; then
  ok "fanz-net exists"
else
  warn "fanz-net does not exist yet"
fi

if command -v ss >/dev/null 2>&1; then
  if ss -ltn | awk '{print $4}' | grep -Eq '(^|:)8085$'; then
    warn "port 8085 is already in use"
  else
    ok "port 8085 appears available"
  fi
else
  warn "ss command unavailable; port check skipped"
fi

echo
echo "--- GPU capability ---"

if command -v nvidia-smi >/dev/null 2>&1; then
  ok "NVIDIA driver detected"
  nvidia-smi --query-gpu=name,driver_version,memory.total \
    --format=csv,noheader 2>/dev/null || true
else
  warn "no NVIDIA GPU tooling detected"
fi

echo
echo "=== PREFLIGHT RESULT ==="

if [ "${fail}" -eq 0 ]; then
  echo "PREFLIGHT PASSED"
else
  echo "PREFLIGHT FAILED"
  exit 1
fi
