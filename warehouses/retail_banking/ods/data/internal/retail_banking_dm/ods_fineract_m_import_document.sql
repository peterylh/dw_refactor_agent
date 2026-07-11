-- Deterministic smoke data for Fineract m_import_document
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_import_document;

INSERT INTO retail_banking_dm.ods_fineract_m_import_document (
    `id`,
    `document_id`,
    `import_time`,
    `end_time`,
    `entity_type`,
    `completed`,
    `total_records`,
    `success_count`,
    `failure_count`,
    `createdby_id`,
    `load_time`
) VALUES
    (
        1,
        1,
        '2025-01-15 09:00:00',
        '2025-01-15 09:00:00',
        1,
        FALSE,
        1,
        1,
        1,
        1,
        '2025-01-15 00:00:00'
    );
