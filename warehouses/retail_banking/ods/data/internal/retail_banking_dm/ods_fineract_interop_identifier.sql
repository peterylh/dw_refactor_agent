-- Deterministic smoke data for Fineract interop_identifier
TRUNCATE TABLE retail_banking_dm.ods_fineract_interop_identifier;

INSERT INTO retail_banking_dm.ods_fineract_interop_identifier (
    `id`,
    `account_id`,
    `type`,
    `a_value`,
    `sub_value_or_type`,
    `created_by`,
    `created_on`,
    `modified_by`,
    `modified_on`,
    `load_time`
) VALUES
    (
        1,
        1,
        'interop_identifier_type_1',
        'interop_identifier_a_value_1',
        'interop_identifier_sub_value_or_type_1',
        'interop_identifier_created_by_1',
        '2025-01-15 09:00:00',
        'interop_identifier_modified_by_1',
        '2025-01-15 09:00:00',
        '2025-01-15 00:00:00'
    );
