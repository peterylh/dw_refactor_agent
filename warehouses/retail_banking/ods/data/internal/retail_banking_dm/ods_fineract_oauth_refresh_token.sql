-- Deterministic smoke data for Fineract oauth_refresh_token
TRUNCATE TABLE retail_banking_dm.ods_fineract_oauth_refresh_token;

INSERT INTO retail_banking_dm.ods_fineract_oauth_refresh_token (
    `token_id`,
    `token`,
    `authentication`,
    `load_time`
) VALUES
    (
        'SYNTHETIC_REDACTED',
        'SYNTHETIC_REDACTED',
        'oauth_refresh_token_authentication_1',
        '2025-01-15 00:00:00'
    );
