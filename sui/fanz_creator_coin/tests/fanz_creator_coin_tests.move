#[test_only]
module fanz_creator_coin::fanz_creator_coin_tests {
    use fanz_creator_coin::fanz_creator_coin;

    #[test]
    fun version_is_one() {
        assert!(
            fanz_creator_coin::version() == 1,
            0,
        );
    }

    #[test]
    fun decimals_are_six() {
        assert!(
            fanz_creator_coin::decimals() == 6,
            1,
        );
    }

    #[test]
    fun genesis_supply_is_21_billion() {
        assert!(
            fanz_creator_coin::genesis_supply_base_units()
                == 21_000_000_000_000_000,
            2,
        );
    }
}
