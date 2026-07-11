-- Deterministic smoke data for Fineract m_entity_to_entity_access
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_entity_to_entity_access;

INSERT INTO retail_banking_dm.ods_fineract_m_entity_to_entity_access (
    `id`,
    `entity_type`,
    `entity_id`,
    `access_type_code_value_id`,
    `second_entity_type`,
    `second_entity_id`,
    `load_time`
) VALUES
    (
        1,
        'm_entity_to_entity_access_entity_type_1',
        1,
        1,
        'm_entity_to_entity_access_second_entity_type_1',
        1,
        '2025-01-15 00:00:00'
    );
