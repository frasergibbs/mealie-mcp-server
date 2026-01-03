# OAuth Server Configuration

This directory contains the OAuth 2.1 authorization server setup using ory/hydra.

## Structure

- `hydra.yml` - Hydra configuration
- `consent-ui/` - Login and consent user interface
- `db/` - PostgreSQL init scripts

## Quick Start

1. Start OAuth infrastructure:
   ```bash
   docker compose up hydra hydra-migrate postgres -d
   ```

2. Verify Hydra is running:
   ```bash
   curl http://localhost:4444/.well-known/openid-configuration
   ```

3. Start consent UI:
   ```bash
   cd consent-ui && python app.py
   ```

## Endpoints

- **Public API**: http://localhost:4444 (OAuth endpoints for clients)
- **Admin API**: http://localhost:4445 (Management, internal only)
- **Consent UI**: http://localhost:3000 (Login/consent flows)

## Configuration

See `../.env.example` for required environment variables.
