-- Deterministic smoke data for Fineract stretchy_parameter
TRUNCATE TABLE retail_banking_dm.ods_fineract_stretchy_parameter;

INSERT INTO retail_banking_dm.ods_fineract_stretchy_parameter (
    `id`,
    `parameter_name`,
    `parameter_variable`,
    `parameter_label`,
    `parameter_displayType`,
    `parameter_FormatType`,
    `parameter_default`,
    `special`,
    `selectOne`,
    `selectAll`,
    `parameter_sql`,
    `parent_id`,
    `load_time`
) VALUES
    (
        1,
        'stretchy_parameter_parameter_name_1',
        'stretchy_parameter_parameter_variable_1',
        'stretchy_parameter_parameter_label_1',
        'stretchy_parameter_parameter_displayType_1',
        'stretchy_p',
        'stretchy_parameter_parameter_default_1',
        's',
        's',
        's',
        'stretchy_parameter_parameter_sql_1',
        1,
        '2025-01-15 00:00:00'
    );
