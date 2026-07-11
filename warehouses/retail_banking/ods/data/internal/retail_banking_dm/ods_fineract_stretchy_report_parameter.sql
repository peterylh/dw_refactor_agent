-- Deterministic smoke data for Fineract stretchy_report_parameter
TRUNCATE TABLE retail_banking_dm.ods_fineract_stretchy_report_parameter;

INSERT INTO retail_banking_dm.ods_fineract_stretchy_report_parameter (
    `id`,
    `report_id`,
    `parameter_id`,
    `report_parameter_name`,
    `load_time`
) VALUES
    (
        1,
        1,
        1,
        'stretchy_report_parameter_report_parameter_na',
        '2025-01-15 00:00:00'
    );
