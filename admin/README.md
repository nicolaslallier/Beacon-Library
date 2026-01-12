# Admin Services for Beacon Library

This directory contains the Docker Compose configuration and supporting files for the admin services stack.

## Quick Start

```bash
# Start admin services
make admin-up

# Stop admin services
make admin-down

# View admin service logs
make admin-logs

# Show all access URLs
make admin-status
```

## Services Overview

| Service | Port | Purpose |
|---------|------|---------|
| **pgAdmin** | 5050 | PostgreSQL database management |
| **Redis Commander** | 8081 | Redis cache inspection |
| **ChromaDB Admin** | 8083 | Vector database management |
| **Ollama WebUI** | 8082 | LLM model management |
| **Nginx Proxy Manager** | 8888 | Reverse proxy admin |
| **MailHog** | 8025 | Email testing (already in main stack) |
| **Gotenberg** | 3100 | Document conversion (health check) |

## Access URLs

### Database Management
- **pgAdmin**: http://localhost:5050
  - Email: `admin@beacon.local`
  - Password: `admin` (or `$PGADMIN_PASSWORD`)

### Cache Management
- **Redis Commander**: http://localhost:8081
  - No authentication by default

### Vector Database (ChromaDB)
- **ChromaDB Admin**: http://localhost:8083
  - Browse collections and embeddings
  - View document counts
  - Monitor indexing status

### LLM Management
- **Ollama WebUI**: http://localhost:8082
  - View loaded models
  - Pull new models
  - Test embeddings

### Email Testing
- **MailHog**: http://localhost:8025
  - View captured emails

### Reverse Proxy Admin
- **Nginx Proxy Manager**: http://localhost:8888
  - Default login: `admin@example.com` / `changeme`
  - Change password on first login

### Admin API Endpoints

```bash
# Get application settings
curl http://localhost:8181/api/admin/settings

# Check all services health
curl http://localhost:8181/api/admin/services/health

# Get services statistics
curl http://localhost:8181/api/admin/services/stats

# Get maintenance statistics
curl http://localhost:8181/api/admin/maintenance/stats

# List ChromaDB collections
curl http://localhost:8181/api/admin/chromadb/collections

# List Ollama models
curl http://localhost:8181/api/admin/ollama/models

# Trigger reindex (POST)
curl -X POST http://localhost:8181/api/admin/chromadb/reindex \
  -H "Content-Type: application/json" \
  -d '{"force": true}'

# Run cleanup (dry run)
curl -X POST http://localhost:8181/api/admin/maintenance/cleanup \
  -H "Content-Type: application/json" \
  -d '{"dry_run": true}'
```

## Configuration

### Environment Variables

You can customize ports and credentials via environment variables:

```bash
# pgAdmin
PGADMIN_PORT=5050
PGADMIN_EMAIL=admin@beacon.local
PGADMIN_PASSWORD=admin

# Redis Commander
REDIS_COMMANDER_PORT=8081
REDIS_COMMANDER_USER=     # Optional HTTP auth
REDIS_COMMANDER_PASSWORD= # Optional HTTP auth

# ChromaDB Admin
CHROMADB_ADMIN_PORT=8083

# Ollama WebUI
OLLAMA_WEBUI_PORT=8082

# Nginx Proxy Manager
NPM_ADMIN_PORT=8888
NPM_HTTP_PORT=8880
NPM_HTTPS_PORT=8443
```

### pgAdmin Pre-configured Server

The `pgadmin/servers.json` file pre-configures the PostgreSQL connection:
- Server Name: `Beacon Library DB`
- Host: `postgres` (Docker network)
- Port: `5432`
- Database: `beacon_library`
- User: `beacon_user`

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Admin Services Stack                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │   pgAdmin   │  │   Redis     │  │     ChromaDB Admin      │ │
│  │   :5050     │  │  Commander  │  │        :8083            │ │
│  └──────┬──────┘  │   :8081     │  └───────────┬─────────────┘ │
│         │         └──────┬──────┘              │               │
│         ▼                ▼                     ▼               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │ PostgreSQL  │  │    Redis    │  │       ChromaDB          │ │
│  │   :5432     │  │   :6379     │  │        :8000            │ │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘ │
│                                                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │   Ollama    │  │   MailHog   │  │    Nginx Proxy Mgr      │ │
│  │   WebUI     │  │   :8025     │  │        :8888            │ │
│  │   :8082     │  └─────────────┘  └─────────────────────────┘ │
│  └──────┬──────┘                                               │
│         ▼                                                      │
│  ┌─────────────┐                                               │
│  │   Ollama    │                                               │
│  │  :11434     │                                               │
│  └─────────────┘                                               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Security Notes

1. **Admin services are NOT started by default** - They run under the `admin` Docker Compose profile
2. **All admin UIs are only accessible on localhost** - No external exposure by default
3. **Change default passwords** before deploying to any shared environment
4. **Admin API endpoints** should be protected with authentication in production

## Troubleshooting

### Services not starting
```bash
# Check if main services are running first
make ps

# Check admin service logs
make admin-logs
```

### pgAdmin can't connect to PostgreSQL
1. Ensure PostgreSQL is healthy: `docker compose ps postgres`
2. Check the password in `servers.json` matches your `.env`

### ChromaDB Admin shows no collections
1. Ensure ChromaDB is running: `docker compose ps chromadb`
2. Check if files have been indexed yet

### Ollama WebUI shows no models
1. Ensure Ollama is running: `docker compose ps ollama`
2. Pull the embedding model: `docker exec beacon-library-ollama ollama pull nomic-embed-text`
