# FANZ Deployment Architecture

This directory contains the reusable FANZ deployment architecture.

## Principles

- Keep the proven production application stack intact while the reusable deployment package is developed.
- Base application services:
  - PostgreSQL
  - Django / Gunicorn
  - nginx
  - auction worker
- Keep secrets outside Git in `.env`.
- Keep payment infrastructure logically separate from the FANZ application stack.
- Support optional GPU/AI and payment-node profiles.
- Avoid host-specific usernames, IP addresses, container names, and legacy Umbrel assumptions.
- Preserve persistent database and media data independently of application containers.

## Current Production Reference

The current production stack remains defined by the repository-root:

- `docker-compose.yml`
- `Dockerfile`
- `nginx/default.conf`
- `deploy.sh`

These files should not be replaced until the reusable architecture has been tested independently.
