-- Deterministic smoke data for Fineract m_loan_term_variations
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_loan_term_variations;

INSERT INTO retail_banking_dm.ods_fineract_m_loan_term_variations (
    `id`,
    `loan_id`,
    `term_type`,
    `applicable_date`,
    `decimal_value`,
    `date_value`,
    `is_specific_to_installment`,
    `applied_on_loan_status`,
    `is_active`,
    `parent_id`,
    `created_on_utc`,
    `created_by`,
    `last_modified_by`,
    `last_modified_on_utc`,
    `load_time`
) VALUES
    (
        1,
        1,
        1,
        '2025-01-15',
        1,
        '2025-01-15',
        FALSE,
        300,
        FALSE,
        1,
        '2025-01-15 09:00:00',
        1,
        1,
        '2025-01-15 09:00:00',
        '2025-01-15 00:00:00'
    );
