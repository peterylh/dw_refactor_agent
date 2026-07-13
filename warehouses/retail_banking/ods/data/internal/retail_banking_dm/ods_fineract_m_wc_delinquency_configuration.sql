-- Deterministic smoke data for Fineract m_wc_delinquency_configuration
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_wc_delinquency_configuration;

INSERT INTO retail_banking_dm.ods_fineract_m_wc_delinquency_configuration (
    `id`,
    `created_by`,
    `last_modified_by`,
    `bucket_id`,
    `frequency`,
    `frequency_type`,
    `minimum_payment`,
    `minimum_payment_type`,
    `created_on_utc`,
    `last_modified_on_utc`,
    `load_time`
) VALUES
    (
        1,
        1,
        1,
        1,
        1,
        'm_wc_delinquency_configuration_frequency_type_1',
        1,
        'm_wc_delinquency_configuration_minimum_payment_typ',
        '2025-01-15 09:00:00',
        '2025-01-15 09:00:00',
        '2025-01-15 00:00:00'
    );
