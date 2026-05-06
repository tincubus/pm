#!/usr/bin/env bash
set -euo pipefail

IMAGE_NAME="pm-mvp"
CONTAINER_NAME="pm-mvp"
PORT="${PORT:-8000}"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required but not installed."
  exit 1
fi

docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true

docker build -t "$IMAGE_NAME" .

if [[ -f ".env" ]]; then
  CONTAINER_ID="$(docker run -d \
    --name "$CONTAINER_NAME" \
    -p "${PORT}:8000" \
    --env-file ".env" \
    "$IMAGE_NAME")"
else
  CONTAINER_ID="$(docker run -d \
    --name "$CONTAINER_NAME" \
    -p "${PORT}:8000" \
    "$IMAGE_NAME")"
fi

echo "Container started: ${CONTAINER_NAME}"
echo "Container id: ${CONTAINER_ID}"

HEALTH_URL="http://localhost:${PORT}/api/health"
MAX_ATTEMPTS=20
ATTEMPT=1

while [[ "$ATTEMPT" -le "$MAX_ATTEMPTS" ]]; do
  if curl -fsS "$HEALTH_URL" >/dev/null 2>&1; then
    echo "Server is ready at http://localhost:${PORT}"
    exit 0
  fi
  sleep 1
  ATTEMPT=$((ATTEMPT + 1))
done

echo "Server did not become ready at ${HEALTH_URL} within ${MAX_ATTEMPTS}s."
echo "Recent container logs:"
docker logs --tail 100 "$CONTAINER_NAME" || true
exit 1
