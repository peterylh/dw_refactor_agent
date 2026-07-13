-- Deterministic smoke data for Fineract m_entity_datatable_check
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_entity_datatable_check;

INSERT INTO retail_banking_dm.ods_fineract_m_entity_datatable_check (
    `id`,
    `application_table_name`,
    `x_registered_table_name`,
    `status_enum`,
    `system_defined`,
    `product_id`,
    `load_time`
) VALUES
    (
        1,
        'm_entity_datatable_check_application_table_name_1',
        'm_entity_datatable_check_x_registered_table_name_1',
        1,
        FALSE,
        1,
        '2025-01-15 00:00:00'
    );
