-- Deterministic smoke data for Fineract m_deposit_product_term_and_preclosure
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_deposit_product_term_and_preclosure;

INSERT INTO retail_banking_dm.ods_fineract_m_deposit_product_term_and_preclosure (
    `id`,
    `savings_product_id`,
    `min_deposit_term`,
    `max_deposit_term`,
    `min_deposit_term_type_enum`,
    `max_deposit_term_type_enum`,
    `in_multiples_of_deposit_term`,
    `in_multiples_of_deposit_term_type_enum`,
    `pre_closure_penal_applicable`,
    `pre_closure_penal_interest`,
    `pre_closure_penal_interest_on_enum`,
    `min_deposit_amount`,
    `max_deposit_amount`,
    `deposit_amount`,
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
        100.000000,
        100.000000,
        100.000000,
        '2025-01-15 00:00:00'
    );
