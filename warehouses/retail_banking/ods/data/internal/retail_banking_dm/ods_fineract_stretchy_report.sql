-- Deterministic smoke data for Fineract stretchy_report
TRUNCATE TABLE retail_banking_dm.ods_fineract_stretchy_report;

INSERT INTO retail_banking_dm.ods_fineract_stretchy_report (
    `id`,
    `report_name`,
    `report_type`,
    `report_subtype`,
    `report_category`,
    `report_sql`,
    `description`,
    `core_report`,
    `use_report`,
    `self_service_user_report`,
    `load_time`
) VALUES
    (
        1,
        'stretchy_report_report_name_1',
        'stretchy_report_repo',
        'stretchy_report_repo',
        'stretchy_report_report_category_1',
        'stretchy_report_report_sql_1',
        'stretchy_report_description_1',
        FALSE,
        FALSE,
        FALSE,
        '2025-01-15 00:00:00'
    );
