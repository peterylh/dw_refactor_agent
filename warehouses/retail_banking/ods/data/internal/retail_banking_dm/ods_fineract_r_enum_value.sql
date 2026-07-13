-- Deterministic smoke data for Fineract r_enum_value
TRUNCATE TABLE retail_banking_dm.ods_fineract_r_enum_value;

INSERT INTO retail_banking_dm.ods_fineract_r_enum_value (
    `enum_name`,
    `enum_id`,
    `enum_message_property`,
    `enum_value`,
    `enum_type`,
    `load_time`
) VALUES
    (
        'r_enum_value_enum_name_1',
        1,
        'r_enum_value_enum_message_property_1',
        'r_enum_value_enum_value_1',
        FALSE,
        '2025-01-15 00:00:00'
    );
