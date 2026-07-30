# FANZ Architecture Principles

Version: 1.0
Date: July 2026

---

## Purpose

These principles guide how FANZ capabilities are designed, connected, and extended.

They complement `PLATFORM_CAPABILITIES.md` and the capability dependency graph.

---

## Platform Identity

FANZ is an AI-powered Business & Creator Operating System.

Discovery is the distribution engine that connects its capabilities.

Posts, businesses, updates, events, auctions, creators, media, and AI experiences all contribute to living Discovery destinations.

---

## 1. Build Capabilities Once

A capability should be implemented once and reused by many object types.

Before creating a new model or workflow, ask whether an existing capability can be extended.

---

## 2. One Canonical Record

A piece of content should have one canonical database record.

It may appear in many feeds, profiles, search results, hashtag pages, Discovery Hubs, and external previews without being duplicated.

One piece of content may have many destinations.

---

## 3. Discovery Hubs Aggregate

Discovery Hubs organize and present existing platform content.

They do not copy posts, images, businesses, events, auctions, or creators into separate content records.

Hub content is retrieved dynamically through capabilities and relationships.

---

## 4. Public Content Feeds Discovery

Only free, public, eligible content may enter community feeds and Discovery Hubs.

Premium or private content remains inside the creator or user experience by design.

Content that does not enter Discovery cannot trigger external Discovery syndication.

---

## 5. Promote Living Destinations

External syndication promotes the canonical Discovery Hub URL rather than an individual post.

A Discovery Hub remains useful after syndication because it continuously accumulates eligible content in newest-to-oldest order.

---

## 6. One Upload, Many Appearances

An uploaded image is stored once as the canonical media asset.

The same stored asset may be rendered in many pages and feeds.

Separate derivative files should be created only for intentional purposes such as thumbnails or branded social-preview graphics.

---

## 7. Optimize Images Before Storage

Every active permanent image-upload surface should use the shared FANZ image-processing capability.

The processor validates the upload, corrects orientation, resizes it, converts it to optimized WebP, and returns the processed file for permanent storage.

The original upload remains temporary unless a documented capability explicitly requires preservation.

---

## 8. Syndication Is Controlled Per Hub

X.com and Pinterest syndication must be throttled per Discovery Hub and per platform.

The platform must support:

- minimum hours between syndications;
- a rolling 24-hour maximum per hub;
- optional platform-wide limits;
- environment-controlled feature flags;
- audit history and idempotency.

A code-level minimum of one hour must remain enforced for X.com and Pinterest.

Telegram may use a separate, less restrictive policy.

---

## 9. Real Activity Triggers Promotion

Cooldown expiration alone does not trigger a social post.

A new eligible content event after the cooldown makes the Discovery Hub eligible for another syndication.

Content received during the cooldown is not lost because it already appears on the living hub page.

---

## 10. AI Consumes Capabilities

AI is a consumer of FANZ capabilities, not a replacement for them.

A Discovery Hub assistant should combine:

1. a configured system prompt;
2. a configured personality;
3. live eligible hub content;
4. an optional curated knowledge base.

AI should retrieve current user content when answering. It should not permanently learn from or memorize user posts.

---

## 11. Lower Layers Stay Independent

Lower-level capabilities must not depend on higher-level experiences.

Identity, media, publishing, permissions, and analytics should remain reusable foundations.

Discovery and AI may consume these capabilities without reversing the dependency direction.

---

## 12. Extend Before Specializing

Avoid industry-specific architecture when reusable platform capabilities can solve the problem.

Restaurants, tourism, real estate, schools, churches, creators, and future industries should assemble experiences from the same capability library.

---

## FANZ Design Test

Before accepting a new feature, ask:

- Is it a reusable capability?
- Can another object or industry use it?
- Does it preserve canonical records?
- Can Discovery consume it?
- Can AI consume it later?
- Does it comply with the shared media and publishing standards?

If the answers are yes, it belongs in FANZ.
