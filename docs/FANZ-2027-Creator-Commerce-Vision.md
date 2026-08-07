# FANZ 2027 -- Creator Commerce Vision

## Purpose

This document captures the long-term vision for FANZ so that
architectural decisions made during 2026 continue to support future
creator-commerce features.

------------------------------------------------------------------------

# 2026 Priority

Complete the multilingual platform foundation.

Current focus:

-   Businesses
-   Discovery
-   Hashtags
-   Events
-   Auctions
-   Feed Posts

Supported languages:

-   English
-   Spanish
-   Portuguese

Goal:

> One platform. Three languages.

------------------------------------------------------------------------

# 2027 Vision

## Create Once. Sell Everywhere.

Creators publish a single product while FANZ presents localized
storefronts to buyers in English, Spanish, and Portuguese.

Examples:

-   eBooks
-   AI Prompt Packs
-   AI Art
-   Music
-   Drum Loops
-   Courses
-   Coloring Books
-   Templates
-   Videos
-   Audiobooks

------------------------------------------------------------------------

# Core Architecture

## Translation Pattern

Every major creator object should eventually support:

Original Object ↓ Translation Table

Examples:

-   AuctionTranslation
-   FeedPostTranslation
-   BusinessUpdateTranslation
-   DigitalProductTranslation
-   LegalDocumentTranslation

------------------------------------------------------------------------

# AI Publishing Assistant

Future workflow:

Create ↓ Translate ↓ Generate hashtags ↓ Generate SEO ↓ Generate social
posts ↓ Review ↓ Publish

The creator always controls the final published version.

------------------------------------------------------------------------

# Multilingual Discovery

One product should appear through localized discovery.

Examples:

EN: - #drumloops - #housemusic

ES: - #loopsdebatería - #musicahouse

PT: - #loopsdebateria - #musichouse

Long-term objective:

Translate concepts, not only words.

------------------------------------------------------------------------

# Audio

Use Kokoro TTS to generate optional localized narration.

Possible outputs:

-   MP3
-   M4B
-   Audiobook editions
-   Product narration

Generated once and cached.

------------------------------------------------------------------------

# Legal

Future legal documents should use versioned translations.

Example:

Terms of Service

Version 1

-   English
-   Spanish
-   Portuguese

Users accept a specific version and language.

------------------------------------------------------------------------

# Long-Term Product Types

-   Auctions
-   Digital Products
-   Businesses
-   Events
-   Music
-   Videos
-   Prompt Packs
-   AI Art
-   Courses
-   Audiobooks

One creator. One listing. Multiple languages.

------------------------------------------------------------------------

# Guiding Principle

Create once.

Reach three markets.

Help creators earn more with less effort by lowering the barriers to
publishing, localization, and discovery across the Americas.
