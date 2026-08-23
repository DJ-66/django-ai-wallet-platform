# FANZ Post-Cutover AI & Security Checkpoint

**Checkpoint:** 2026-08-23  
**Host:** `fanzto`  
**Production:** `https://fanz.to`

## Git / Application

- Branch: `phase12-search-knowledge-graph`
- Production HEAD: `64b1cbe` — Connect FANZ app and Ollama over fanz-net
- Working tree verified clean and synchronized with origin.
- Relevant deployment commits:
  - `443ca7a` — Make AI providers deployment configurable
  - `48f6b22` — Add reusable FANZ deployment architecture
  - `0883d63` — Fix Ollama GPU healthcheck
  - `64b1cbe` — Connect FANZ app and Ollama over fanz-net

## Production Application

- FANZ services healthy:
  - PostgreSQL
  - Django / Gunicorn
  - nginx
  - auction worker
- Public `https://fanz.to` verified HTTP 200.
- Django system check: no issues.
- Database fingerprint:
  - users: 107
  - founder_accounts: 45

## AI / GPU

- NVIDIA GeForce RTX 3060 12 GB operational.
- NVIDIA driver: 595.84.
- Docker GPU passthrough verified.
- Ollama: `0.32.14`.
- Model: `gemma3:latest`.
- Gemma 3 model ID: `a2af6cc3eb7f`.
- Model size reported by Ollama: approximately 2.9 GB loaded.
- Runtime processor: 100% GPU.
- Ollama and FANZ communicate over external Docker network `fanz-net`.
- Production Ollama endpoint:
  `http://ollama:11434/api/chat`
- FANZ live provider inference verified successfully.
- OpenAI SDK `1.109.1` installed in the current FANZ application image.
- Historical `local_deepseek` provider values remain supported and route through the Ollama-backed local provider.

## Security Hardening

- PostgreSQL production password rotated.
- `DATABASE_URL` updated to the rotated PostgreSQL credential.
- Django `SECRET_KEY` rotated.
- Temporary rotation files removed after successful validation.
- Username/password authentication verified after rotation.
- Google OAuth verified after rotation.
- Gemma/Ollama verified after rotation.
- Old Umbrel remains preserved as rollback infrastructure.

## Recovery Backups

### Latest authoritative runtime backup

`~/stacks/backups/backup-2026-08-23-0146.sql.gz`

- Actual filesystem timestamp: `2026-08-23 04:46:33 UTC`
- SHA-256:
  `ba9b6a8fddfaaf588a73e4a045e2f133c654057896d531e112bfc4eccbdfbf39`
- gzip integrity: OK
- PostgreSQL dump version: 16.15
- Note: filename timestamp does not match the actual filesystem timestamp; use the full filename and actual timestamp when identifying this backup.

### Explicit post-rotation checkpoint

`~/stacks/backups/fanz-post-rotation-2026-08-23-0436.sql.gz`

- SHA-256:
  `ae22694b8b3b28027dbdf90505baac2b0fa9bc6c55f6be1732ec076b710051ac`
- gzip integrity: OK

### Original production-cutover backup

`~/stacks/backups/backup-2026-08-22-0201.sql.gz`

- SHA-256:
  `8e485cdf789fc21109054db9893804e6237993b88142037565b697589597691c`
- gzip integrity: OK

## Recovery Chain

The current retained recovery chain is:

1. Original production cutover — 2026-08-22
2. Explicit post-security-rotation checkpoint — 2026-08-23
3. Latest authoritative runtime backup — 2026-08-23 04:46 UTC

## Current Status

FANZ production is healthy after:

- production tower cutover
- reusable deployment architecture creation
- GPU/Ollama activation
- Gemma 3 GPU validation
- durable FANZ/Ollama networking
- PostgreSQL credential rotation
- Django SECRET_KEY rotation
- authentication validation
- post-rotation recovery backup

The old Umbrel environment remains intact as rollback protection.
