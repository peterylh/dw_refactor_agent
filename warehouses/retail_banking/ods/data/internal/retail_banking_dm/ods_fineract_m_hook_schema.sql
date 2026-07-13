-- Deterministic smoke data for Fineract m_hook_schema
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_hook_schema;

INSERT INTO retail_banking_dm.ods_fineract_m_hook_schema (
    `id`,
    `hook_template_id`,
    `field_type`,
    `field_name`,
    `placeholder`,
    `optional`,
    `load_time`
) VALUES
    (
        1,
        1,
        'm_hook_schema_field_type_1',
        'm_hook_schema_field_name_1',
        'm_hook_schema_placeholder_1',
        FALSE,
        '2025-01-15 00:00:00'
    );
