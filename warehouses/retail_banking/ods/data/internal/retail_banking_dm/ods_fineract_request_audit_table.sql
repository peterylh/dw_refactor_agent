-- Deterministic smoke data for Fineract request_audit_table
TRUNCATE TABLE retail_banking_dm.ods_fineract_request_audit_table;

INSERT INTO retail_banking_dm.ods_fineract_request_audit_table (
    `id`,
    `lastname`,
    `username`,
    `mobile_number`,
    `firstname`,
    `authentication_token`,
    `password`,
    `email`,
    `client_id`,
    `created_date`,
    `account_number`,
    `load_time`
) VALUES
    (
        1,
        'Synthetic request_audit_table 1',
        'request_audit_table_username_1',
        '15500000001',
        'Synthetic request_audit_table 1',
        'SYNTHETIC_REDACTED',
        'SYNTHETIC_REDACTED',
        'user1@example.com',
        1,
        '2025-01-15',
        'A000000001',
        '2025-01-15 00:00:00'
    );
