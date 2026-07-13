-- Deterministic smoke data for Fineract c_external_service_properties
TRUNCATE TABLE retail_banking_dm.ods_fineract_c_external_service_properties;

INSERT INTO retail_banking_dm.ods_fineract_c_external_service_properties (
    `name`,
    `value`,
    `external_service_id`,
    `load_time`
) VALUES
    (
        'Synthetic c_external_service_properties 1',
        'c_external_service_properties_value_1',
        1,
        '2025-01-15 00:00:00'
    );
