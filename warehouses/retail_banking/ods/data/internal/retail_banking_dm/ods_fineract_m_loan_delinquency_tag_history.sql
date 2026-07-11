-- Deterministic smoke data for Fineract m_loan_delinquency_tag_history
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_loan_delinquency_tag_history;

INSERT INTO retail_banking_dm.ods_fineract_m_loan_delinquency_tag_history (
    `id`,
    `delinquency_range_id`,
    `loan_id`,
    `addedon_date`,
    `liftedon_date`,
    `created_by`,
    `created_on_utc`,
    `version`,
    `last_modified_by`,
    `last_modified_on_utc`,
    `load_time`
) VALUES
    (
        1,
        1,
        1,
        '2025-01-15',
        '2025-01-15',
        1,
        '2025-01-15 09:00:00',
        1,
        1,
        '2025-01-15 09:00:00',
        '2025-01-15 00:00:00'
    );
