#!/bin/bash

set -euo pipefail

ENV_FILE="${ENV_FILE:-.env.docker}"

if [ ! -f "$ENV_FILE" ] && [ -f ".env" ]; then
    ENV_FILE=".env"
fi

if [ -f "$ENV_FILE" ]; then
    echo "Loading Compose environment from ${ENV_FILE}"
    set -a
    # shellcheck disable=SC1090
    case "$ENV_FILE" in
        /*|./*|../*) ENV_FILE_PATH="$ENV_FILE" ;;
        *) ENV_FILE_PATH="./$ENV_FILE" ;;
    esac
    . "$ENV_FILE_PATH"
    set +a
else
    echo "No .env.docker or .env found. Using shell environment and Compose defaults."
fi

PORT="${OPENEMR_MCP_PORT:-8305}"
PATH_VALUE="${OPENEMR_MCP_PATH:-/mcp}"
NETWORK_NAME="${OPENEMR_DOCKER_NETWORK:-openemr_default}"

echo "Starting openemr-mcp with Docker Compose..."
echo "External network: ${NETWORK_NAME}"

if ! docker network inspect "${NETWORK_NAME}" >/dev/null 2>&1; then
    echo "Creating missing external Docker network: ${NETWORK_NAME}"
    docker network create "${NETWORK_NAME}" >/dev/null
fi

docker compose up -d --build

echo "Container is up at: http://127.0.0.1:${PORT}${PATH_VALUE}"
echo "Logs: docker compose logs -f openemr-mcp"
