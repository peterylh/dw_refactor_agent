-- Deterministic smoke data for Fineract m_business_date
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_business_date;

INSERT INTO retail_banking_dm.ods_fineract_m_business_date (
    `id`,
    `type`,
    `date`,
    `created_by`,
    `created_date`,
    `version`,
    `last_modified_by`,
    `lastmodified_date`,
    `created_on_utc`,
    `last_modified_on_utc`,
    `load_time`
) VALUES
    (
        1,
        'm_business_date_type_1',
        '2025-01-15',
        1,
        '2025-01-15 09:00:00',
        1,
        1,
        '2025-01-15 09:00:00',
        '2025-01-15 09:00:00',
        '2025-01-15 09:00:00',
        '2025-01-15 00:00:00'
    );
