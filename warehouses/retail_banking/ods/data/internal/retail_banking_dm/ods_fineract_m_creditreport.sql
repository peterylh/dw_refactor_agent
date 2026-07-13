-- Deterministic smoke data for Fineract m_creditreport
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_creditreport;

INSERT INTO retail_banking_dm.ods_fineract_m_creditreport (
    `id`,
    `credit_bureau_id`,
    `national_id`,
    `credit_reports`,
    `load_time`
) VALUES
    (
        1,
        1,
        'm_creditreport_national_id_1',
        'm_creditreport_credit_reports_1',
        '2025-01-15 00:00:00'
    );
