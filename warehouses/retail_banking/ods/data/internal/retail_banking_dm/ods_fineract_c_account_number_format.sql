-- Deterministic smoke data for Fineract c_account_number_format
TRUNCATE TABLE retail_banking_dm.ods_fineract_c_account_number_format;

INSERT INTO retail_banking_dm.ods_fineract_c_account_number_format (
    `id`,
    `account_type_enum`,
    `prefix_type_enum`,
    `prefix_character`,
    `load_time`
) VALUES
    (
        1,
        1,
        1,
        'c_account_number_format_prefix_character_1',
        '2025-01-15 00:00:00'
    );
