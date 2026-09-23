# FANZ Phase 14 → TokenGate Creator Engine Restart Brief

## Status

FANZ Phase 14 autonomous creator publisher is LIVE and should be left running.

Branch:

`phase14-auto-publisher`

Latest checkpoints:

- `35d9a03` — ground vision creator copy in visible details
- `7307381` — add vision-aware creator post copy
- `9f8fa87` — automatically replenish creator publication queue
- `42f09d6` — maintain rolling AI publication queue
- `3f5b78e` — show all managed platform accounts
- `b18c515` — enable scheduled AI creator publishing

Final test state: **25 Phase 14 tests passing**.

## Production State

46 AI creator identities are active.

Publishing behavior:

- approximately one creator post every ~31 minutes
- approximately one post per creator per 24 hours
- randomized creator rotation
- exactly one pending publication per creator
- `auction_worker` publishes due rows automatically
- replenisher runs approximately once per minute
- published source media is consumed
- avatar media is reserved/excluded
- any `explicit/` directory is excluded from public auto-posting
- normal FANZ FeedPost processing remains authoritative

Latest health snapshot:

- total ScheduledPublication rows: 54
- published: 8
- queued: 46
- publishing: 0
- failed: 0
- pending: 46

## Vision Copy

Local Ollama is running:

- model: `gemma3:latest`
- Gemma 3 4.3B Q4_K_M
- vision capable
- GPU: NVIDIA RTX 3060 12 GB

Production setting:

`CREATOR_VISION_COPY_ENABLED=True`

New replenished posts use:

image → Gemma vision → grounded title/caption → approved hashtags.

Validation/fallback:

- strict JSON
- title <= 60 chars
- approved hashtag pool only
- 4 vision-selected tags
- deterministic creator identity tag
- `#FANZ`
- invalid/unavailable vision falls back to proven template copy

Prompt explicitly avoids invented emotions/preferences and favors visible details.

Production autonomous vision proof:

- Lizzy row 17 published → source consumed
- Lizzy row 52 automatically replenished for +24h
- row 52 title: `Terracotta & Denim`
- row 52 uses vision copy, not template copy
- Coquette also published and worker logged `copy=vision` while automatically creating her next row

Do NOT tune titles/copy immediately. Let the system run for at least a full rotation and review real output first.

## FANZ Product Boundary

Keep this implementation **platform-only on FANZ**.

No FANZ vending/customer product is required now.

FANZ uses the system internally to:

- keep the feed active
- demonstrate FANZ creator capabilities
- encourage free FANZ signups
- expose users to tips, auctions, AI chat, sell posts, business updates, etc.
- eventually manufacture image/video expansion packs internally

FANZ may later use ComfyUI/SDXL internally for media manufacturing.

## Next Phase — TokenGate Creator Engine

Do NOT move/remove the working FANZ publisher.

Clone the proven behavior into standalone TokenGate as a generic Dockerized white-label capability.

Target TG Creator Engine:

- CreatorIdentity
- MediaPack / MediaAsset
- safe/private/reserved asset policies
- vision/LLM copy provider
- scheduling
- exactly-one-pending invariant
- replenishment
- publisher adapter interface
- usage metering
- Docker deployment

FANZ becomes a publisher/white-label integration, not TG's core implementation.

### BYOG

TG white-label customers supply their own GPU/models/storage/electricity.

Optional local-AI stack:

- Ollama / Gemma
- ComfyUI
- SDXL image workflows
- styles / filters
- TTS
- optional video workflows

Reference hardware: RTX 3060 **12 GB VRAM**.

Image generation is practical (~seconds per image in current workflows).
Video generation is much heavier (~minutes for a short clip), so FANZ video remains in-house for now; TG video can be BYOG.

## Tomorrow's First Task

Start in:

`~/stacks/tokengate`

First inspect the existing standalone TG repo/service and design the Creator Engine domain/schema + usage metering before copying implementation code.

Keep FANZ running untouched while TG Creator Engine is developed separately.
