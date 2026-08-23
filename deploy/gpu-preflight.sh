#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_COMPOSE="${SCRIPT_DIR}/docker-compose.base.yml"
GPU_COMPOSE="${SCRIPT_DIR}/docker-compose.gpu.yml"
ENV_FILE="${SCRIPT_DIR}/.env"

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

echo "=== FANZ GPU PREFLIGHT ==="
echo

echo "--- NVIDIA host driver ---"

if command -v nvidia-smi >/dev/null 2>&1; then
  ok "nvidia-smi available"
  nvidia-smi \
    --query-gpu=name,driver_version,memory.total \
    --format=csv,noheader
else
  bad "nvidia-smi unavailable"
fi

echo
echo "--- Docker GPU passthrough ---"

if docker run --rm --gpus all \
    nvidia/cuda:12.8.0-base-ubuntu24.04 \
    nvidia-smi \
    --query-gpu=name,memory.total \
    --format=csv,noheader >/tmp/fanz-gpu-check.$$ 2>&1; then

  ok "Docker can access NVIDIA GPU"
  cat /tmp/fanz-gpu-check.$$
else
  bad "Docker GPU passthrough failed"
  cat /tmp/fanz-gpu-check.$$ || true
fi

rm -f /tmp/fanz-gpu-check.$$

echo
echo "--- Ollama compose image ---"

if grep -q 'ollama/ollama:0.32.14' "${GPU_COMPOSE}"; then
  ok "Ollama image pinned to 0.32.14"
else
  bad "expected Ollama image pin not found"
fi

echo
echo "--- Compose validation ---"

cleanup_env=false

if [ ! -f "${ENV_FILE}" ]; then
  cp "${SCRIPT_DIR}/.env.example" "${ENV_FILE}"
  cleanup_env=true
fi

if docker compose \
    --env-file "${ENV_FILE}" \
    -f "${BASE_COMPOSE}" \
    -f "${GPU_COMPOSE}" \
    config --quiet; then
  ok "base + GPU compose configuration valid"
else
  bad "base + GPU compose configuration invalid"
fi

echo
echo "--- Ollama wiring ---"

resolved_url="$(
  docker compose \
    --env-file "${ENV_FILE}" \
    -f "${BASE_COMPOSE}" \
    -f "${GPU_COMPOSE}" \
    config 2>/dev/null \
    | grep 'OLLAMA_URL:' \
    | head -1 \
    | awk '{print $2}'
)"

if [ "${resolved_url}" = "http://ollama:11434/api/chat" ]; then
  ok "FANZ resolves Ollama through compose network"
else
  bad "unexpected OLLAMA_URL: ${resolved_url:-missing}"
fi

if [ "${cleanup_env}" = "true" ]; then
  rm -f "${ENV_FILE}"
fi

echo
echo "=== GPU PREFLIGHT RESULT ==="

if [ "${fail}" -eq 0 ]; then
  echo "GPU PREFLIGHT PASSED"
else
  echo "GPU PREFLIGHT FAILED"
  exit 1
fi
