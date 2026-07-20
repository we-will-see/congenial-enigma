# VPS deployment

This package runs Enigma, PostgreSQL/pgvector, migrations, company seeding, OCR, health checks, and persistent storage with Docker Compose.

## VPS requirements

- Ubuntu 22.04/24.04 or another modern Linux distribution
- Docker Engine with the Docker Compose plugin
- At least 2 CPU cores, 4 GB RAM, and 20 GB disk for an initial test
- SSH access

## First deployment

```bash
git clone https://github.com/we-will-see/congenial-enigma.git
cd congenial-enigma
git switch agent/enigma-document-intelligence-mvp
./deploy/vps-up.sh
```

The helper creates a private `.env` with a random PostgreSQL password, builds the API image, starts both services, applies Alembic migrations, seeds companies, and waits for the health check.

The safe default binds the API to the VPS loopback interface. From your computer:

```bash
ssh -L 8000:127.0.0.1:8000 <user>@<vps-ip>
```

Then open `http://127.0.0.1:8000/docs` and use the interactive API.

## Public test access

The API does not yet include user authentication. Do not expose it broadly with private documents.

For a temporary public test, change this line in `.env`:

```dotenv
BIND_ADDRESS=0.0.0.0
```

Then restrict TCP port 8000 to your own IP using the VPS firewall and restart:

```bash
docker compose up -d
```

For a durable deployment, place Caddy or Nginx with HTTPS and authentication in front of the loopback-bound API.

## Configure semantic retrieval

Keyword notebook retrieval works without an external key. To enable embeddings and hybrid retrieval, add an OpenAI key to `.env`:

```dotenv
OPENAI_API_KEY=...
```

Then recreate the API container:

```bash
docker compose up -d --force-recreate api
```

## Operations

```bash
# Status and health
docker compose ps

# Follow API logs
docker compose logs -f api

# Rebuild after pulling code
git pull
docker compose up -d --build

# Stop services but retain all data
./deploy/vps-down.sh

# Remove services and all database/document volumes (destructive)
docker compose down --volumes
```

PostgreSQL data is stored in the `postgres_data` volume. Uploaded source documents are stored in `document_data`. Back up both before upgrades that change storage or migrations.
