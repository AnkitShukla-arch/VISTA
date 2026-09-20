#!/usr/bin/env bash
# VISTA phase-1 Docker management (MinIO data lake).
# Usage: bash manage_vista.sh up|down|status|reset
set -euo pipefail
cd "$(dirname "$0")"

case "${1:-}" in
  up)
    docker compose up -d --wait
    echo ""
    echo "MinIO API     -> http://localhost:${MINIO_PORT:-9000}"
    echo "MinIO console -> http://localhost:${MINIO_CONSOLE_PORT:-9001}"
    ;;
  down)
    docker compose down
    ;;
  status)
    docker compose ps
    ;;
  reset)
    docker compose down -v   # destroys the MinIO volume
    docker compose up -d --wait
    ;;
  *)
    echo "Usage: bash manage_vista.sh up|down|status|reset" >&2
    exit 1
    ;;
esac
