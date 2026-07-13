-- Deterministic smoke data for Fineract m_delinquency_bucket_mappings
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_delinquency_bucket_mappings;

INSERT INTO retail_banking_dm.ods_fineract_m_delinquency_bucket_mappings (
    `id`,
    `delinquency_range_id`,
    `delinquency_bucket_id`,
    `created_by`,
    `created_on_utc`,
    `version`,
    `last_modified_by`,
    `last_modified_on_utc`,
    `load_time`
) VALUES
    (
        1,
        1,
        1,
        1,
        '2025-01-15 09:00:00',
        1,
        1,
        '2025-01-15 09:00:00',
        '2025-01-15 00:00:00'
    );
