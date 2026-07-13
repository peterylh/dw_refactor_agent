-- Deterministic smoke data for Fineract m_creditbureau
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_creditbureau;

INSERT INTO retail_banking_dm.ods_fineract_m_creditbureau (
    `id`,
    `name`,
    `product`,
    `country`,
    `implementation_key`,
    `load_time`
) VALUES
    (
        1,
        'Synthetic m_creditbureau 1',
        'm_creditbureau_product_1',
        'US',
        'm_creditbureau_implementation_key_1',
        '2025-01-15 00:00:00'
    );
