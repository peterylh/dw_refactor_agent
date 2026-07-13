-- Deterministic smoke data for Fineract m_field_configuration
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_field_configuration;

INSERT INTO retail_banking_dm.ods_fineract_m_field_configuration (
    `id`,
    `entity`,
    `subentity`,
    `field`,
    `is_enabled`,
    `is_mandatory`,
    `validation_regex`,
    `load_time`
) VALUES
    (
        1,
        'm_field_configuration_entity_1',
        'm_field_configuration_subentity_1',
        'm_field_configuration_field_1',
        FALSE,
        FALSE,
        'm_field_configuration_validation_regex_1',
        '2025-01-15 00:00:00'
    );
