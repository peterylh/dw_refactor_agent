-- Deterministic smoke data for Fineract m_loan_status_change_history
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_loan_status_change_history;

INSERT INTO retail_banking_dm.ods_fineract_m_loan_status_change_history (
    `id`,
    `loan_id`,
    `status_code`,
    `status_change_business_date`,
    `created_by`,
    `last_modified_by`,
    `created_on_utc`,
    `last_modified_on_utc`,
    `load_time`
) VALUES
    (
        1,
        1,
        'm_loan_status_change_history_status_code_1',
        '2025-01-15',
        1,
        1,
        '2025-01-15 09:00:00',
        '2025-01-15 09:00:00',
        '2025-01-15 00:00:00'
    );
