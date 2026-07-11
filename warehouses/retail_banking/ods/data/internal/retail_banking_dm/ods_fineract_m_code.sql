-- Deterministic smoke data for Fineract m_code
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_code;

INSERT INTO retail_banking_dm.ods_fineract_m_code (
    `id`,
    `code_name`,
    `is_system_defined`,
    `load_time`
) VALUES
    (
        1,
        'm_code_code_name_1',
        FALSE,
        '2025-01-15 00:00:00'
    );
