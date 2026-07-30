# FANZ Platform Actions

Updated: July 2026

---

## Discovery Hub v2 — Living Discovery

### Foundation

- [x] Discovery Hub models
- [x] Localized Discovery Hub translations
- [x] Dynamic template selection
- [x] Discovery Home
- [x] Business-to-Discovery association
- [x] Remove duplicate Discovery detail URL
- [x] Route Discovery Hub hero images through the shared WebP pipeline
- [x] Route localized Discovery hero images through the shared WebP pipeline

### Dynamic Hub Content

- [ ] Add newest-first public, free hashtag posts
- [ ] Add related businesses
- [ ] Add upcoming published events
- [ ] Add relevant active auctions
- [ ] Add participating creators
- [ ] Add empty states for each content section
- [ ] Add pagination or incremental loading
- [ ] Add canonical URL metadata
- [ ] Add Open Graph and social-preview metadata
- [ ] Verify multilingual fallback behavior
- [ ] Verify mobile presentation

### Content Rules

- [ ] Reuse the existing `FeedPost` record across all destinations
- [ ] Include only `is_public=True`
- [ ] Include only `is_paid=False`
- [ ] Match active hubs by normalized hashtags
- [ ] Allow one post to appear in multiple matching hubs
- [ ] Ensure removed or moderated content cannot appear
- [ ] Define maximum hashtags considered for external syndication
- [ ] Define platform-wide hashtag normalization rules

---

## Discovery Syndication Engine

### Core Pipeline

- [ ] Create Discovery syndication event model
- [ ] Create platform delivery/audit model
- [ ] Trigger hub-update events after eligible public post creation
- [ ] Key deduplication by platform and Discovery Hub
- [ ] Promote the Discovery Hub canonical URL
- [ ] Preserve the triggering post ID for audit purposes
- [ ] Add idempotency protection
- [ ] Add safe retry handling
- [ ] Add delivery-status administration
- [ ] Add syndication analytics

### Configuration

- [ ] Add Telegram enable flag
- [ ] Add X.com enable flag
- [ ] Add Pinterest enable flag
- [ ] Add per-platform minimum-hours settings
- [ ] Enforce a hard one-hour minimum for X.com and Pinterest
- [ ] Add rolling 24-hour maximum per hub
- [ ] Add optional platform-wide rolling limits
- [ ] Add configurable retry count
- [ ] Add configurable retry delay

### Trigger Policy

- [ ] Do not syndicate premium or private content
- [ ] Do not syndicate merely because a cooldown expired
- [ ] Require new eligible activity after the cooldown
- [ ] Allow each matching hub to evaluate independently
- [ ] Allow a multi-hashtag post to trigger multiple eligible hubs
- [ ] Do not create delayed catch-up posts when no new activity occurs

### Platforms

- [ ] Telegram channel integration
- [ ] X.com integration
- [ ] Pinterest integration
- [ ] FANZ-branded Pinterest creative generation
- [ ] UTM parameters per platform and hub
- [ ] Platform error and policy monitoring

---

## Discovery AI

- [ ] Use the configured localized system prompt
- [ ] Use the configured AI personality
- [ ] Retrieve live public/free hub posts
- [ ] Retrieve related businesses
- [ ] Retrieve upcoming events
- [ ] Retrieve active auctions
- [ ] Retrieve relevant creators
- [ ] Add optional curated knowledge-base sources
- [ ] Exclude premium/private content from AI context
- [ ] Add source attribution to AI answers
- [ ] Add context-size and freshness controls

---

## Platform Image Standard

### Current Coverage

- [x] Feed post images
- [x] Feed media images
- [x] Auction Studio images
- [x] Business hero images
- [x] Business updates
- [x] Business gallery images
- [x] Event images
- [x] User avatars
- [x] Profile banners
- [x] Payment QR images
- [x] Discovery Hub hero images
- [x] Discovery Hub translation hero images

### Follow-up

- [ ] Audit every active image upload surface
- [ ] Ignore historical migration declarations during active-flow audits
- [ ] Document intentional exceptions
- [ ] Verify old-file deletion when an image is replaced
- [ ] Verify file deletion when a record is deleted
- [ ] Centralize named image presets
- [ ] Add processor tests for dimensions, type, orientation, and size
- [ ] Add upload-limit tests
- [ ] Monitor media-storage growth
