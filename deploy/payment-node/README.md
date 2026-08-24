# FANZ Private Payment Infrastructure

This directory contains the reusable private payment infrastructure profile
for the FANZ platform.

## Purpose

This infrastructure exists only to support FANZ platform payment processing.

It is not intended to provide public hosted wallets, public cryptocurrency
accounts, or custodial wallets for FANZ users.

## Core Principles

- Payment infrastructure remains logically separate from the FANZ application stack.
- Payment services have their own lifecycle, persistence, backup, and recovery procedures.
- FANZ must remain operational even when cryptocurrency payment infrastructure is unavailable.
- Secrets remain outside Git in `.env`.
- Backend node RPC, databases, and administrative interfaces are not publicly exposed.
- Host-specific usernames, IP addresses, and legacy Umbrel assumptions are avoided.

## Platform Payments

FANZ may operate private infrastructure to process payments where the FANZ
platform itself is the recipient.

Initial payment categories include:

- Bitcoin (BTC)
- Dogecoin (DOGE)
- FANZ Credits
- Other payment methods added deliberately in the future

Blockchain payments and FANZ Credits remain separate accounting systems.

A confirmed cryptocurrency payment may trigger FANZ application business logic,
but cryptocurrency balances must not be represented as FANZ Credits until the
application explicitly performs the corresponding ledger operation.

## FANZ Credits

FANZ Credits are an internal application ledger.

They are not an on-chain cryptocurrency wallet and do not require Bitcoin,
Dogecoin, BTCPay, or Lightning infrastructure to function.

## User-Owned Payment Destinations

FANZ users may provide their own payment information for display on the platform.

Examples may include:

- BTC address or QR information
- DOGE address or QR information
- Other supported external payment destinations

These destinations remain controlled by the user.

FANZ may store and display the information necessary to facilitate a direct
payment, but FANZ does not create or custody a cryptocurrency wallet for the
user as part of this payment-node profile.

Payments to user-provided destinations go directly to those destinations rather
than through a public FANZ-hosted wallet service.

## BTCPay Boundary

Any BTCPay Server deployment used by FANZ is private platform infrastructure.

It must not operate as a public wallet or public address-hosting service for
FANZ users.

BTCPay administrative services must not be exposed unnecessarily.

Whether BTCPay Server is required for the final architecture will be determined
after evaluating the simplest reliable platform-processing model.

## Lightning

The initial FANZ payment architecture does not operate Lightning payment
channels.

No active LND channels are required.

Lightning infrastructure is outside the scope of the initial payment-node
deployment.

## Bitcoin

Bitcoin infrastructure may be used to:

- verify FANZ platform BTC payments
- observe transactions relevant to FANZ-controlled payment destinations
- provide the blockchain backend required by the selected private payment processor

Bitcoin infrastructure is not intended to provide public FANZ-hosted wallets.

## Dogecoin

Dogecoin support is treated as a separate blockchain integration.

The final DOGE architecture must define:

- node/backend requirements
- payment detection
- confirmation policy
- FANZ application integration
- persistence
- backup and recovery

DOGE support must not be assumed to behave identically to the Bitcoin/BTCPay
integration.

## Network Boundary

Payment infrastructure should use a private Docker network for internal service
communication.

Only the service or API requiring communication with FANZ should additionally
join the external `fanz-net`.

Blockchain RPC interfaces, databases, and internal payment services should not
be exposed to `fanz-net` unless explicitly required.

## Persistence

Persistent payment infrastructure must survive container replacement.

Storage boundaries will be defined separately for:

- Bitcoin node data
- Dogecoin node data
- payment processor data
- payment database data
- configuration and recovery material

Payment storage must remain independent from the FANZ application PostgreSQL
database and application containers.

## Current Status

Architecture definition only.

No payment-node services should be deployed until the BTC, DOGE, FANZ Credits,
networking, persistence, backup, and recovery models have been reviewed and
validated.
