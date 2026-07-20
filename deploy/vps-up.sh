#!/bin/sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT_DIR"

if ! command -v docker >/dev/null 2>&1; then
    echo "Docker is required. Install Docker Engine with the Compose plugin, then run this command again." >&2
    exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
    echo "The Docker Compose plugin is required." >&2
    exit 1
fi

if [ ! -f .env ]; then
    cp .env.vps.example .env
    if command -v openssl >/dev/null 2>&1; then
        DB_PASSWORD=$(openssl rand -hex 24)
    else
        DB_PASSWORD=$(od -An -N24 -tx1 /dev/urandom | tr -d ' \n')
    fi
    sed -i "s/^POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=$DB_PASSWORD/" .env
    chmod 0600 .env
    echo "Created .env with a generated database password."
fi

if grep -q '^POSTGRES_PASSWORD=CHANGE_ME$' .env; then
    echo "Replace POSTGRES_PASSWORD=CHANGE_ME in .env before deployment." >&2
    exit 1
fi

docker compose up -d --build --remove-orphans

CONTAINER_ID=$(docker compose ps -q api)
if [ -z "$CONTAINER_ID" ]; then
    echo "The API container was not created." >&2
    docker compose logs --tail=100
    exit 1
fi

echo "Waiting for Enigma to become healthy..."
ATTEMPT=0
while [ "$ATTEMPT" -lt 60 ]; do
    STATUS=$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}starting{{end}}' "$CONTAINER_ID")
    if [ "$STATUS" = "healthy" ]; then
        PORT=$(sed -n 's/^APP_PORT=//p' .env | tail -n 1)
        PORT=${PORT:-8000}
        BIND=$(sed -n 's/^BIND_ADDRESS=//p' .env | tail -n 1)
        BIND=${BIND:-127.0.0.1}
        echo ""
        echo "Enigma is healthy."
        echo "API docs on the VPS: http://$BIND:$PORT/docs"
        if [ "$BIND" = "127.0.0.1" ]; then
            echo "From your computer, open an SSH tunnel:"
            echo "  ssh -L $PORT:127.0.0.1:$PORT <user>@<vps-ip>"
            echo "Then visit: http://127.0.0.1:$PORT/docs"
        fi
        exit 0
    fi
    if [ "$STATUS" = "unhealthy" ]; then
        echo "Enigma became unhealthy." >&2
        docker compose logs --tail=150 api postgres
        exit 1
    fi
    ATTEMPT=$((ATTEMPT + 1))
    sleep 2
done

echo "Timed out waiting for Enigma." >&2
docker compose logs --tail=150 api postgres
exit 1
