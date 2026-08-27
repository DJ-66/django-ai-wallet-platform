#[test_only]
module fanz_creator_coin::fanz_creator_coin_tests {
    use fanz_creator_coin::fanz_creator_coin;

    #[test]
    fun version_is_one() {
        assert!(fanz_creator_coin::version() == 1, 0);
    }
}
