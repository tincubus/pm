#!/usr/bin/env bash
set -euo pipefail

CONTAINER_NAME="pm-mvp"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required but not installed."
  exit 1
fi

docker stop "$CONTAINER_NAME" >/dev/null 2>&1 || true
docker rm "$CONTAINER_NAME" >/dev/null 2>&1 || true

echo "Container stopped and removed: ${CONTAINER_NAME}"
