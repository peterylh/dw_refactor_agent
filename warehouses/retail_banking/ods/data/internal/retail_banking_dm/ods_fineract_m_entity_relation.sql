-- Deterministic smoke data for Fineract m_entity_relation
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_entity_relation;

INSERT INTO retail_banking_dm.ods_fineract_m_entity_relation (
    `id`,
    `from_entity_type`,
    `to_entity_type`,
    `code_name`,
    `load_time`
) VALUES
    (
        1,
        1,
        1,
        'm_entity_relation_code_name_1',
        '2025-01-15 00:00:00'
    );
