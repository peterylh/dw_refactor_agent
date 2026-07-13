-- Deterministic smoke data for Fineract m_floating_rates
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_floating_rates;

INSERT INTO retail_banking_dm.ods_fineract_m_floating_rates (
    `id`,
    `name`,
    `is_base_lending_rate`,
    `is_active`,
    `created_by`,
    `created_date`,
    `last_modified_by`,
    `lastmodified_date`,
    `created_on_utc`,
    `last_modified_on_utc`,
    `load_time`
) VALUES
    (
        1,
        'Synthetic m_floating_rates 1',
        FALSE,
        FALSE,
        1,
        '2025-01-15 09:00:00',
        1,
        '2025-01-15 09:00:00',
        '2025-01-15 09:00:00',
        '2025-01-15 09:00:00',
        '2025-01-15 00:00:00'
    );
