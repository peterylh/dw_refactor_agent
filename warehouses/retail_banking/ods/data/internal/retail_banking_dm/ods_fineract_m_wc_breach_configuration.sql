-- Deterministic smoke data for Fineract m_wc_breach_configuration
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_wc_breach_configuration;

INSERT INTO retail_banking_dm.ods_fineract_m_wc_breach_configuration (
    `id`,
    `name`,
    `breach_frequency`,
    `breach_frequency_type`,
    `breach_amount_calculation_type`,
    `breach_amount`,
    `load_time`
) VALUES
    (
        1,
        'Synthetic m_wc_breach_configuration 1',
        1,
        'm_wc_breach_configuration_breach_frequency_type_1',
        'm_wc_breach_configuration_breach_amount_calculatio',
        100.000000,
        '2025-01-15 00:00:00'
    );
