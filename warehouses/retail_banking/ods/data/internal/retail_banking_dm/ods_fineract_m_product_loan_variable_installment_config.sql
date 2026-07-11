-- Deterministic smoke data for Fineract m_product_loan_variable_installment_config
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_product_loan_variable_installment_config;

INSERT INTO retail_banking_dm.ods_fineract_m_product_loan_variable_installment_config (
    `id`,
    `loan_product_id`,
    `minimum_gap`,
    `maximum_gap`,
    `load_time`
) VALUES
    (
        1,
        1,
        1,
        1,
        '2025-01-15 00:00:00'
    );
