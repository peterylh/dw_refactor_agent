-- Deterministic smoke data for Fineract m_delinquency_bucket
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_delinquency_bucket;

INSERT INTO retail_banking_dm.ods_fineract_m_delinquency_bucket (
    `id`,
    `name`,
    `created_by`,
    `created_on_utc`,
    `version`,
    `last_modified_by`,
    `last_modified_on_utc`,
    `bucket_type`,
    `load_time`
) VALUES
    (
        1,
        'Synthetic m_delinquency_bucket 1',
        1,
        '2025-01-15 09:00:00',
        1,
        1,
        '2025-01-15 09:00:00',
        'm_delinquency_bucket_bucket_type_1',
        '2025-01-15 00:00:00'
    );
