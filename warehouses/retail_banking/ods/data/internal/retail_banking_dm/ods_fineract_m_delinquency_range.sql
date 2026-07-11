-- Deterministic smoke data for Fineract m_delinquency_range
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_delinquency_range;

INSERT INTO retail_banking_dm.ods_fineract_m_delinquency_range (
    `id`,
    `classification`,
    `min_age_days`,
    `max_age_days`,
    `created_by`,
    `created_on_utc`,
    `version`,
    `last_modified_by`,
    `last_modified_on_utc`,
    `load_time`
) VALUES
    (
        1,
        'm_delinquency_range_classification_1',
        1,
        1,
        1,
        '2025-01-15 09:00:00',
        1,
        1,
        '2025-01-15 09:00:00',
        '2025-01-15 00:00:00'
    );
