-- Deterministic smoke data for Fineract m_floating_rates_periods
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_floating_rates_periods;

INSERT INTO retail_banking_dm.ods_fineract_m_floating_rates_periods (
    `id`,
    `floating_rates_id`,
    `from_date`,
    `interest_rate`,
    `is_differential_to_base_lending_rate`,
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
        1,
        '2025-01-15',
        100.000000,
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
