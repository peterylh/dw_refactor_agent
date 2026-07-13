-- Deterministic smoke data for Fineract m_external_event
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_external_event;

INSERT INTO retail_banking_dm.ods_fineract_m_external_event (
    `id`,
    `type`,
    `created_at`,
    `status`,
    `business_date`,
    `data`,
    `idempotency_key`,
    `sent_at`,
    `schema`,
    `category`,
    `aggregate_root_id`,
    `load_time`
) VALUES
    (
        1,
        'm_external_event_type_1',
        '2025-01-15 09:00:00',
        'm_external_event_status_1',
        '2025-01-15',
        'm_external_event_data_1',
        'm_external_event_idempotency_key_1',
        '2025-01-15 09:00:00',
        'm_external_event_schema_1',
        'm_external_event_category_1',
        1,
        '2025-01-15 00:00:00'
    );
