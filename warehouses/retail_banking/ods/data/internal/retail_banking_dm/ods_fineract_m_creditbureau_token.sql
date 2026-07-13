-- Deterministic smoke data for Fineract m_creditbureau_token
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_creditbureau_token;

INSERT INTO retail_banking_dm.ods_fineract_m_creditbureau_token (
    `id`,
    `username`,
    `token`,
    `token_type`,
    `expires_in`,
    `issued`,
    `expiry_date`,
    `load_time`
) VALUES
    (
        1,
        'm_creditbureau_token_username_1',
        'SYNTHETIC_REDACTED',
        'SYNTHETIC_REDACTED',
        'm_creditbureau_token_expires_in_1',
        'm_creditbureau_token_issued_1',
        '2025-01-15',
        '2025-01-15 00:00:00'
    );
