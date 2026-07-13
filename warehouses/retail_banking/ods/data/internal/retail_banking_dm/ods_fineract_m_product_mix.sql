-- Deterministic smoke data for Fineract m_product_mix
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_product_mix;

INSERT INTO retail_banking_dm.ods_fineract_m_product_mix (
    `id`,
    `product_id`,
    `restricted_product_id`,
    `load_time`
) VALUES
    (
        1,
        1,
        1,
        '2025-01-15 00:00:00'
    );
