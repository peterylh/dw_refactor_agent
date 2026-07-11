-- Deterministic smoke data for Fineract m_entity_to_entity_mapping
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_entity_to_entity_mapping;

INSERT INTO retail_banking_dm.ods_fineract_m_entity_to_entity_mapping (
    `id`,
    `rel_id`,
    `from_id`,
    `to_id`,
    `start_date`,
    `end_date`,
    `load_time`
) VALUES
    (
        1,
        1,
        1,
        1,
        '2025-01-15',
        '2025-01-15',
        '2025-01-15 00:00:00'
    );
