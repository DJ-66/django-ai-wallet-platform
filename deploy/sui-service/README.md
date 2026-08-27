# FANZ Sui Service

Private chain-adapter boundary for FANZ creator/community economy assets.

## v0 scope

This initial service is intentionally a mock adapter.

It:

- accepts durable FANZ economy delivery obligations
- journals them independently from the Django database
- enforces `submission_key` idempotency
- rejects conflicting reuse of a submission key
- returns a mock `prepared` state
- persists its journal across container replacement
- exposes no host/public port

It does **not**:

- connect to Sui
- contain a Sui private key
- sign transactions
- submit transactions
- move coins

## Network boundary

Only the API service joins the external `fanz-net`.

FANZ may reach it internally at:

`http://fanz-sui:3000`

No host port should be published.

## Idempotency contract

`submission_key` is immutable and unique.

A repeated request with the same key and identical immutable delivery data
returns the existing delivery.

A repeated key with different asset, recipient, or amount is rejected with
HTTP 409.

## Future phases

1. mock adapter
2. Sui testnet transaction construction
3. external signer integration
4. durable signed-transaction reconciliation
5. transaction confirmation
6. FANZ PaymentIntent completion
7. mainnet only after testnet/recovery validation
