-- Deterministic smoke data for Fineract x_registered_table
TRUNCATE TABLE retail_banking_dm.ods_fineract_x_registered_table;

INSERT INTO retail_banking_dm.ods_fineract_x_registered_table (
    `registered_table_name`,
    `application_table_name`,
    `entity_subtype`,
    `category`,
    `load_time`
) VALUES
    (
        'x_registered_table_registered_table_name_1',
        'x_registered_table_application_table_name_1',
        'x_registered_table_entity_subtype_1',
        1,
        '2025-01-15 00:00:00'
    );
