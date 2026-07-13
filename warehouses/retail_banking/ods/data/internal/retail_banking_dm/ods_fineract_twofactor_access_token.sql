-- Deterministic smoke data for Fineract twofactor_access_token
TRUNCATE TABLE retail_banking_dm.ods_fineract_twofactor_access_token;

INSERT INTO retail_banking_dm.ods_fineract_twofactor_access_token (
    `id`,
    `token`,
    `appuser_id`,
    `valid_from`,
    `valid_to`,
    `enabled`,
    `load_time`
) VALUES
    (
        1,
        'SYNTHETIC_REDACTED',
        1,
        '2025-01-15 09:00:00',
        '2025-01-15 09:00:00',
        FALSE,
        '2025-01-15 00:00:00'
    );
