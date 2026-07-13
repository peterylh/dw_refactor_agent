-- Deterministic smoke data for Fineract m_product_loan_rate
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_product_loan_rate;

INSERT INTO retail_banking_dm.ods_fineract_m_product_loan_rate (
    `product_loan_id`,
    `rate_id`,
    `load_time`
) VALUES
    (
        1,
        1,
        '2025-01-15 00:00:00'
    );
