-- Deterministic smoke data for Fineract m_document
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_document;

INSERT INTO retail_banking_dm.ods_fineract_m_document (
    `id`,
    `parent_entity_type`,
    `parent_entity_id`,
    `name`,
    `file_name`,
    `size`,
    `type`,
    `description`,
    `location`,
    `storage_type_enum`,
    `load_time`
) VALUES
    (
        1,
        'm_document_parent_entity_type_1',
        1,
        'Synthetic m_document 1',
        'm_document_file_name_1',
        1,
        'm_document_type_1',
        'm_document_description_1',
        'm_document_location_1',
        1,
        '2025-01-15 00:00:00'
    );
