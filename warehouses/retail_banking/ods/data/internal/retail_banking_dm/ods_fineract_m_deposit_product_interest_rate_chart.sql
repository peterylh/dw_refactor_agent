-- Deterministic smoke data for Fineract m_deposit_product_interest_rate_chart
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_deposit_product_interest_rate_chart;

INSERT INTO retail_banking_dm.ods_fineract_m_deposit_product_interest_rate_chart (
    `deposit_product_id`,
    `interest_rate_chart_id`,
    `load_time`
) VALUES
    (
        1,
        1,
        '2025-01-15 00:00:00'
    );
