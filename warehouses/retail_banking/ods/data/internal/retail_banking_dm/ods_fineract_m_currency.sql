-- Deterministic smoke data for Fineract m_currency
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_currency;

INSERT INTO retail_banking_dm.ods_fineract_m_currency (
    `id`,
    `code`,
    `decimal_places`,
    `currency_multiplesof`,
    `display_symbol`,
    `name`,
    `internationalized_name_code`,
    `load_time`
) VALUES
    (
        1,
        'm_c',
        1,
        1,
        'm_currency',
        'Synthetic m_currency 1',
        'm_currency_internationalized_name_code_1',
        '2025-01-15 00:00:00'
    );
