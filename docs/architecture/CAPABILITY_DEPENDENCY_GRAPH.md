# FANZ Capability Dependency Graph

## Purpose

This document describes the dependency hierarchy of the core platform capabilities.

Lower-level capabilities should never depend on higher-level capabilities.

Higher-level capabilities may consume lower-level capabilities.

---

## Current Dependency Graph

```text
Identity
      │
      ▼
Credits
      │
      ▼
Capability Gates
      │
      ├─────────────┐
      ▼             ▼
Business       Creator
      │             │
      ├──────┐      │
      ▼      ▼      ▼
Updates  Events  Private Posts
      │      │      │
      └──┬───┴──────┘
         ▼
    Entitlements
         │
         ▼
 Creator Commerce
         │
         ▼
 AI Receptionist
```

---

## Rule

Higher-level capabilities may depend upon lower-level capabilities.

Lower-level capabilities should never depend upon higher-level capabilities.

---

## Goal

This graph should grow over time without violating the dependency direction.
