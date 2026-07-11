-- Deterministic smoke data for Fineract m_wc_loan_originator_mapping
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_wc_loan_originator_mapping;

INSERT INTO retail_banking_dm.ods_fineract_m_wc_loan_originator_mapping (
    `id`,
    `loan_id`,
    `originator_id`,
    `created_on_utc`,
    `created_by`,
    `last_modified_on_utc`,
    `last_modified_by`,
    `load_time`
) VALUES
    (
        1,
        1,
        1,
        '2025-01-15 09:00:00',
        1,
        '2025-01-15 09:00:00',
        1,
        '2025-01-15 00:00:00'
    );
