-- Deterministic smoke data for Fineract oauth_access_token
TRUNCATE TABLE retail_banking_dm.ods_fineract_oauth_access_token;

INSERT INTO retail_banking_dm.ods_fineract_oauth_access_token (
    `token_id`,
    `token`,
    `authentication_id`,
    `user_name`,
    `client_id`,
    `authentication`,
    `refresh_token`,
    `load_time`
) VALUES
    (
        'SYNTHETIC_REDACTED',
        'SYNTHETIC_REDACTED',
        'oauth_access_token_authentication_id_1',
        'oauth_access_token_user_name_1',
        'oauth_access_token_client_id_1',
        'oauth_access_token_authentication_1',
        'SYNTHETIC_REDACTED',
        '2025-01-15 00:00:00'
    );
