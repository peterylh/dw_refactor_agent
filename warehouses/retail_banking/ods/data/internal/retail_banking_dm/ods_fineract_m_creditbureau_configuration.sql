-- Deterministic smoke data for Fineract m_creditbureau_configuration
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_creditbureau_configuration;

INSERT INTO retail_banking_dm.ods_fineract_m_creditbureau_configuration (
    `id`,
    `configkey`,
    `value`,
    `organisation_creditbureau_id`,
    `description`,
    `load_time`
) VALUES
    (
        1,
        '{}',
        'm_creditbureau_configuration_value_1',
        1,
        'm_creditbureau_configuration_description_1',
        '2025-01-15 00:00:00'
    );
