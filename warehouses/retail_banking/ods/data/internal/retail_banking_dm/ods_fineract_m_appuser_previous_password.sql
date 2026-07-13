-- Deterministic smoke data for Fineract m_appuser_previous_password
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_appuser_previous_password;

INSERT INTO retail_banking_dm.ods_fineract_m_appuser_previous_password (
    `id`,
    `user_id`,
    `password`,
    `removal_date`,
    `load_time`
) VALUES
    (
        1,
        1,
        'SYNTHETIC_REDACTED',
        '2025-01-15',
        '2025-01-15 00:00:00'
    );
