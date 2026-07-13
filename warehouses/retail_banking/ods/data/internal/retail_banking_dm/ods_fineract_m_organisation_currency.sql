-- Deterministic smoke data for Fineract m_organisation_currency
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_organisation_currency;

INSERT INTO retail_banking_dm.ods_fineract_m_organisation_currency (
    `id`,
    `code`,
    `decimal_places`,
    `currency_multiplesof`,
    `name`,
    `display_symbol`,
    `internationalized_name_code`,
    `load_time`
) VALUES
    (
        1,
        'm_o',
        1,
        1,
        'Synthetic m_organisation_currency 1',
        'm_organisa',
        'm_organisation_currency_internationalized_name_cod',
        '2025-01-15 00:00:00'
    );
