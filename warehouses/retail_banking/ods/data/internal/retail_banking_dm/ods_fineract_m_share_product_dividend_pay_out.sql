-- Deterministic smoke data for Fineract m_share_product_dividend_pay_out
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_share_product_dividend_pay_out;

INSERT INTO retail_banking_dm.ods_fineract_m_share_product_dividend_pay_out (
    `id`,
    `product_id`,
    `amount`,
    `dividend_period_start_date`,
    `dividend_period_end_date`,
    `status`,
    `createdby_id`,
    `created_date`,
    `lastmodifiedby_id`,
    `lastmodified_date`,
    `load_time`
) VALUES
    (
        1,
        1,
        100.000000,
        '2025-01-15',
        '2025-01-15',
        300,
        1,
        '2025-01-15 09:00:00',
        1,
        '2025-01-15 09:00:00',
        '2025-01-15 00:00:00'
    );
