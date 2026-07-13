-- Deterministic smoke data for Fineract m_report_mailing_job_configuration
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_report_mailing_job_configuration;

INSERT INTO retail_banking_dm.ods_fineract_m_report_mailing_job_configuration (
    `id`,
    `name`,
    `value`,
    `load_time`
) VALUES
    (
        1,
        'Synthetic m_report_mailing_job_configuration 1',
        'm_report_mailing_job_configuration_value_1',
        '2025-01-15 00:00:00'
    );
