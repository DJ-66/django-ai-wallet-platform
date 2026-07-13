# ADR 0001: Event Is a Reusable Capability

Date: July 2026

Status: Accepted

## Context

FANZ needs events for businesses, creators, communities, schools, churches, festivals, and future organization types.

A business-specific event model would duplicate logic and limit reuse.

## Decision

FANZ will use one reusable Event capability.

The Event is always owned by its creator.

A business is an optional association.

Future associations may include communities, schools, churches, festivals, and government organizations.

## Model Direction

The Event foundation includes:

- creator
- optional business
- event type
- title
- description
- start and end time
- location
- image
- published state
- cancelled state

## Capability Gate

Creating new events requires the shared capability helper:

```python
can_create_events(user)
