-- Deterministic smoke data for Fineract m_product_loan_variations_borrower_cycle
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_product_loan_variations_borrower_cycle;

INSERT INTO retail_banking_dm.ods_fineract_m_product_loan_variations_borrower_cycle (
    `id`,
    `loan_product_id`,
    `borrower_cycle_number`,
    `value_condition`,
    `param_type`,
    `default_value`,
    `max_value`,
    `min_value`,
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
        '2025-01-15 00:00:00'
    );
