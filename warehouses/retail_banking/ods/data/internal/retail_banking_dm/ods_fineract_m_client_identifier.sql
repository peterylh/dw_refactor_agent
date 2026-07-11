-- Deterministic smoke data for Fineract m_client_identifier
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_client_identifier;

INSERT INTO retail_banking_dm.ods_fineract_m_client_identifier (
    `id`,
    `client_id`,
    `document_type_id`,
    `document_key`,
    `status`,
    `active`,
    `description`,
    `created_by`,
    `last_modified_by`,
    `created_date`,
    `lastmodified_date`,
    `created_on_utc`,
    `last_modified_on_utc`,
    `load_time`
) VALUES
    (
        1,
        1,
        1,
        'm_client_identifier_document_key_1',
        300,
        1,
        'm_client_identifier_description_1',
        1,
        1,
        '2025-01-15 09:00:00',
        '2025-01-15 09:00:00',
        '2025-01-15 09:00:00',
        '2025-01-15 09:00:00',
        '2025-01-15 00:00:00'
    );
