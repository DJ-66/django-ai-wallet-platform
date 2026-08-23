#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
COMPOSE_FILE="${SCRIPT_DIR}/docker-compose.base.yml"
ENV_FILE="${SCRIPT_DIR}/.env"

echo "=== FANZ reusable deployment ==="
echo "Repository: ${REPO_ROOT}"
echo "Compose:    ${COMPOSE_FILE}"
echo "Env:        ${ENV_FILE}"

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker is not installed."
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "ERROR: Docker Compose plugin is not available."
  exit 1
fi

if [ ! -f "${ENV_FILE}" ]; then
  echo "ERROR: ${ENV_FILE} does not exist."
  echo "Create it from:"
  echo "  cp ${SCRIPT_DIR}/.env.example ${ENV_FILE}"
  echo "Then replace all placeholder values."
  exit 1
fi

if grep -Eq 'replace-with-|example\.com|smtp\.example\.com' "${ENV_FILE}"; then
  echo "ERROR: placeholder values remain in ${ENV_FILE}."
  exit 1
fi

read_env_value() {
  local key="$1"
  local default="$2"
  local value

  value="$(grep -E "^${key}=" "${ENV_FILE}" 2>/dev/null | tail -1 | cut -d= -f2- || true)"

  if [ -z "${value}" ]; then
    printf '%s' "${default}"
  else
    value="${value%\"}"
    value="${value#\"}"
    value="${value%\'}"
    value="${value#\'}"
    printf '%s' "${value}"
  fi
}

FANZ_NETWORK="$(read_env_value FANZ_NETWORK fanz-net)"
FANZ_HTTP_PORT="$(read_env_value FANZ_HTTP_PORT 8085)"

echo
echo "Validating compose configuration..."
docker compose \
  --env-file "${ENV_FILE}" \
  -f "${COMPOSE_FILE}" \
  config --quiet

echo "Ensuring Docker network exists: ${FANZ_NETWORK}"
docker network inspect "${FANZ_NETWORK}" >/dev/null 2>&1 \
  || docker network create "${FANZ_NETWORK}"

echo
echo "Building and starting FANZ..."
docker compose \
  --env-file "${ENV_FILE}" \
  -f "${COMPOSE_FILE}" \
  up -d --build

echo
echo "Waiting for FANZ HTTP endpoint..."
ready=false

for i in $(seq 1 30); do
  if curl -fsI "http://127.0.0.1:${FANZ_HTTP_PORT}/auctions/" >/dev/null; then
    ready=true
    break
  fi

  echo "Waiting... ${i}/30"
  sleep 2
done

if [ "${ready}" != "true" ]; then
  echo
  echo "ERROR: FANZ did not become ready."
  docker compose \
    --env-file "${ENV_FILE}" \
    -f "${COMPOSE_FILE}" \
    ps

  docker compose \
    --env-file "${ENV_FILE}" \
    -f "${COMPOSE_FILE}" \
    logs --tail=100 web nginx

  exit 1
fi

echo
echo "=== FANZ deployment healthy ==="

docker compose \
  --env-file "${ENV_FILE}" \
  -f "${COMPOSE_FILE}" \
  ps

echo
echo "Local endpoint:"
curl -fsI "http://127.0.0.1:${FANZ_HTTP_PORT}/auctions/" | head
