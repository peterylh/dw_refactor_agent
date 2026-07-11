-- Deterministic smoke data for Fineract x_table_column_code_mappings
TRUNCATE TABLE retail_banking_dm.ods_fineract_x_table_column_code_mappings;

INSERT INTO retail_banking_dm.ods_fineract_x_table_column_code_mappings (
    `column_alias_name`,
    `code_id`,
    `load_time`
) VALUES
    (
        'x_table_column_code_mappings_column_alias_name_1',
        1,
        '2025-01-15 00:00:00'
    );
