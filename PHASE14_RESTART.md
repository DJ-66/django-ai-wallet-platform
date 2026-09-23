# FANZ Phase 14 → TokenGate Creator Engine — Restart Brief

## Current Checkpoint

FANZ Phase 14 autonomous creator publishing is LIVE in production.

Branch:

`phase14-auto-publisher`

Last known Git state was clean and 13 commits ahead of origin before this restart brief.

Important commits:

- `35d9a03` — ground vision creator copy in visible details
- `7307381` — add vision-aware creator post copy
- `9f8fa87` — automatically replenish creator publication queue
- `42f09d6` — maintain rolling AI publication queue
- `3f5b78e` — show all managed platform accounts
- `b18c515` — enable scheduled AI creator publishing
- `5af84a3` — harden AI creator publishing operations
- `6688ae6` — creator post styles + public media safeguards

Final Phase 14 test checkpoint:

`25 tests passing`

Database backup verified:

`~/stacks/backups/FANZ-2026-09-23-0110.sql.gz`

PostgreSQL dump/version: 16.15.

---

## FANZ Autonomous Creator Publisher

There are **46 AI creator identities**.

Production behavior:

- randomized creator order
- approximately one FANZ creator post every ~31 minutes
- approximately one post per creator every 24 hours
- exactly one pending publication maintained per creator
- `auction_worker` checks due publications about every 10 seconds
- replenishment runs approximately once per minute
- publication source is consumed after successful posting
- generated feed media uses normal FANZ processing/WebP pipeline
- creator tips/wallets work
- creator accounts are manageable through `/platform/accounts/`

Safety/media rules:

- creator avatar source is never auto-posted
- any directory named `explicit` is excluded
- already scheduled/consumed media is excluded
- `.zip` files are not part of creator media ingestion
- failures do not consume source media

Last production health snapshot:

- ScheduledPublication total: 54
- published: 8
- queued: 46
- publishing: 0
- failed: 0
- pending: 46

Leave the FANZ publisher running.

---

## Vision-Aware Creator Copy

FANZ uses local Ollama:

- model: `gemma3:latest`
- Gemma 3 4.3B Q4_K_M
- completion + vision capable
- GPU: NVIDIA RTX 3060
- VRAM: 12 GB
- `CREATOR_VISION_COPY_ENABLED=True`

New replenished publications use:

`safe image → Gemma vision → title + caption + approved hashtags`

Copy rules:

- grounded in visible image details
- no invented sensitive attributes
- no invented locations/events/backstory
- prompt discourages invented emotions/preferences
- title <= 60 characters
- four vision-selected approved hashtags
- deterministic creator identity hashtag
- `#FANZ`
- invalid/unavailable AI falls back to proven template copy

Examples observed:

- ExoticInfluencer: `City Dusk Reflections`
- Lizzy: `Terracotta & Denim`

Lizzy autonomous proof:

- row 17 published successfully
- source consumed
- worker automatically replenished row 52 for +24h
- row 52 used a new safe source
- title/caption were vision-generated, not template copy
- pending invariant returned to 1

Coquette independently proved the full worker path:

`publish → consume source → Gemma vision → copy=vision → create next publication`

Do NOT aggressively tune titles/captions yet.
Let the system run for at least a full rotation and review real production output first.

---

## FANZ Product Boundary

The autonomous creator system stays **platform-only on fanz.to**.

Do NOT build FANZ vending/customer access for it right now.

Purpose of FANZ creator accounts:

- keep FANZ active
- demonstrate platform capabilities
- encourage free FANZ registrations
- expose users to FANZ features such as:
  - auctions
  - tips
  - AI chat
  - sell/premium posts
  - creator profiles
  - digital businesses
  - daily business updates
  - other FANZ capabilities

FANZ may later create custom image/video expansion packs internally.

ComfyUI/SDXL/image/video manufacturing on FANZ remains platform-operated.

---

## Next Product: TokenGate Creator Engine

Do NOT move or remove the working FANZ implementation.

Build a separate TG-native version in:

`~/stacks/tokengate`

TokenGate Creator Engine should reproduce the proven behavior as a generic Dockerized white-label capability.

Target concepts:

- CreatorIdentity
- MediaPack
- MediaAsset
- reserved/private/explicit media policy
- vision/text provider abstraction
- image-aware copy generation
- deterministic fallback
- PublicationSchedule
- PublicationJob
- exactly-one-pending invariant
- automatic replenishment
- PublisherAdapter
- usage metering
- Docker/Compose deployment

FANZ becomes a reference implementation / publisher integration.
Do not simply copy FANZ Django models into TG.

First define the TG-native domain/API boundary.

---

## TG White Label / BYOG Direction

Creator Engine becomes a standard capability for TokenGate white-label customers.

Local AI / Creator Studio is **BYOG — Bring Your Own GPU**.

TG supplies:

- software
- Docker orchestration
- creator automation
- workflows
- scheduling
- publisher adapters
- metering

White-label operator supplies:

- GPU
- models
- storage
- electricity

Optional BYOG stack:

- Ollama
- Gemma
- ComfyUI
- SDXL
- image styles/filters
- TTS
- optional video workflows

Reference hardware:

`NVIDIA RTX 3060 — 12 GB VRAM`

Observed rough local performance:

- SDXL/ComfyUI image workflows: roughly seconds/image (~5 sec observed)
- short video generation: much heavier (~5 min for ~5 sec observed)

Therefore:

- image generation is a strong BYOG fit
- video can remain FANZ in-house initially
- TG video support can be BYOG rather than hosted by FANZ

Do not price the TG feature yet.
Build and meter real usage first; later decide whether pricing should be per-use, day/week/month, credits, or a hybrid.

---

## First Task In New Chat

1. Read this brief.
2. Confirm FANZ should remain untouched/running.
3. Move to `~/stacks/tokengate`.
4. Inspect the existing standalone TG repository/container architecture.
5. Design the smallest TG-native Creator Engine domain + usage-metering boundary.
6. Only then begin implementing/porting the proven FANZ behavior.

Goal:

**Preserve FANZ as the live reference system while building a clean Dockerized TokenGate Creator Engine for white-label BYOG deployments.**
