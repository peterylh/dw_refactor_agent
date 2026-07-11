-- Deterministic smoke data for Fineract m_external_event_configuration
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_external_event_configuration;

INSERT INTO retail_banking_dm.ods_fineract_m_external_event_configuration (
    `type`,
    `enabled`,
    `load_time`
) VALUES
    (
        'm_external_event_configuration_type_1',
        FALSE,
        '2025-01-15 00:00:00'
    );
