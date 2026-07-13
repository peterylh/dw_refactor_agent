-- Deterministic smoke data for Fineract m_wc_loan_range_delinquency_tag
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_wc_loan_range_delinquency_tag;

INSERT INTO retail_banking_dm.ods_fineract_m_wc_loan_range_delinquency_tag (
    `id`,
    `created_by`,
    `last_modified_by`,
    `delinquency_range_id`,
    `loan_id`,
    `range_id`,
    `addedon_date`,
    `liftedon_date`,
    `outstanding_amount`,
    `version`,
    `created_on_utc`,
    `last_modified_on_utc`,
    `load_time`
) VALUES
    (
        1,
        1,
        1,
        1,
        1,
        1,
        '2025-01-15',
        '2025-01-15',
        100.000000,
        1,
        '2025-01-15 09:00:00',
        '2025-01-15 09:00:00',
        '2025-01-15 00:00:00'
    );
