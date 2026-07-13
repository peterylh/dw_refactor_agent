-- Deterministic smoke data for Fineract m_share_product_market_price
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_share_product_market_price;

INSERT INTO retail_banking_dm.ods_fineract_m_share_product_market_price (
    `id`,
    `product_id`,
    `from_date`,
    `share_value`,
    `load_time`
) VALUES
    (
        1,
        1,
        '2025-01-15',
        1,
        '2025-01-15 00:00:00'
    );
