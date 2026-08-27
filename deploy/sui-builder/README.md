# FANZ Sui Builder

Disposable build environment for FANZ Move packages.

## Security boundary

This container:

- contains the Sui / Move compiler toolchain
- may build and test Move source
- does not receive FANZ Sui signer secrets
- is not attached to `fanz-net`
- does not submit transactions
- does not own production or testnet signing authority

Compiled artifacts are reviewed before they are consumed by `fanz-sui`.
