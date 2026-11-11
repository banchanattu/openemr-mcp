#!/bin/bash

set -euo pipefail

ENV_FILE=".env.local"
if [ ! -f "$ENV_FILE" ] && [ -f ".env" ]; then
    ENV_FILE=".env"
fi

echo "Starting openemr-mcp locally..."

if [ -f "$ENV_FILE" ]; then
    echo "Loading environment variables from $ENV_FILE"
    set -a
    # shellcheck disable=SC1090
    case "$ENV_FILE" in
        /*|./*|../*) ENV_FILE_PATH="$ENV_FILE" ;;
        *) ENV_FILE_PATH="./$ENV_FILE" ;;
    esac
    . "$ENV_FILE_PATH"
    set +a
else
    echo "No .env.local or .env found. Using process environment only."
fi

TRANSPORT="${OPENEMR_MCP_TRANSPORT:-streamable-http}"
HOST="${OPENEMR_MCP_HOST:-127.0.0.1}"
PORT="${OPENEMR_MCP_PORT:-8305}"
PATH_VALUE="${OPENEMR_MCP_PATH:-/mcp}"

echo "Server URL: http://${HOST}:${PORT}${PATH_VALUE}"
echo "Press Ctrl+C to stop"

exec uv run openemr-mcp \
    --transport "$TRANSPORT" \
    --host "$HOST" \
    --port "$PORT" \
    --path "$PATH_VALUE"
