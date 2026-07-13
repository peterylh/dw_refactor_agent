-- Deterministic smoke data for Fineract m_deposit_account_term_and_preclosure
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_deposit_account_term_and_preclosure;

INSERT INTO retail_banking_dm.ods_fineract_m_deposit_account_term_and_preclosure (
    `id`,
    `savings_account_id`,
    `min_deposit_term`,
    `max_deposit_term`,
    `min_deposit_term_type_enum`,
    `max_deposit_term_type_enum`,
    `in_multiples_of_deposit_term`,
    `in_multiples_of_deposit_term_type_enum`,
    `pre_closure_penal_applicable`,
    `pre_closure_penal_interest`,
    `pre_closure_penal_interest_on_enum`,
    `deposit_period`,
    `deposit_period_frequency_enum`,
    `deposit_amount`,
    `maturity_amount`,
    `maturity_date`,
    `on_account_closure_enum`,
    `expected_firstdepositon_date`,
    `transfer_interest_to_linked_account`,
    `transfer_to_savings_account_id`,
    `load_time`
) VALUES
    (
        1,
        1,
        1,
        1,
        1,
        1,
        1,
        1,
        FALSE,
        100.000000,
        1,
        1,
        1,
        100.000000,
        100.000000,
        '2025-01-15',
        1,
        '2025-01-15',
        FALSE,
        1,
        '2025-01-15 00:00:00'
    );
