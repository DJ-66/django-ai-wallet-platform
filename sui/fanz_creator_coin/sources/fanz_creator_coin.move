module fanz_creator_coin::fanz_creator_coin {
    use sui::coin::Coin;
    use sui::coin_registry;

    /// FANZ Creator Coin v1.
    ///
    /// Genesis supply:
    ///   21,000,000,000 coins
    ///   6 decimals
    ///   21,000,000,000,000,000 base units
    ///
    /// The entire supply is minted during module initialization.
    /// TreasuryCap is then consumed by make_supply_fixed(),
    /// permanently fixing the total supply.
    ///
    /// MetadataCap survives independently so creator branding may
    /// evolve without changing supply.
    public struct FANZ_CREATOR_COIN has drop {}

    const DECIMALS: u8 = 6;

    const GENESIS_SUPPLY_BASE_UNITS: u64 =
        21_000_000_000_000_000;

    fun init(
        witness: FANZ_CREATOR_COIN,
        ctx: &mut TxContext,
    ) {
        let (
            mut currency,
            mut treasury_cap,
        ) = coin_registry::new_currency_with_otw(
            witness,
            DECIMALS,
            b"FANZ".to_string(),
            b"FANZ Creator Coin".to_string(),
            b"Fixed-supply FANZ creator economy coin".to_string(),
            b"".to_string(),
            ctx,
        );

        // Mint the complete lifetime supply exactly once.
        let genesis_supply: Coin<FANZ_CREATOR_COIN> =
            treasury_cap.mint(
                GENESIS_SUPPLY_BASE_UNITS,
                ctx,
            );

        // Permanently fix supply by consuming TreasuryCap.
        // No future minting or supply reduction through TreasuryCap
        // remains possible.
        currency.make_supply_fixed(treasury_cap);

        // Metadata authority is deliberately independent of supply.
        let metadata_cap = currency.finalize(ctx);

        transfer::public_transfer(
            genesis_supply,
            ctx.sender(),
        );

        transfer::public_transfer(
            metadata_cap,
            ctx.sender(),
        );
    }

    public fun decimals(): u8 {
        DECIMALS
    }

    public fun genesis_supply_base_units(): u64 {
        GENESIS_SUPPLY_BASE_UNITS
    }

    public fun version(): u64 {
        1
    }
}
