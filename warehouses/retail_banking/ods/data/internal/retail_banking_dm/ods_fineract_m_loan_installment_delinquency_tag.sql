-- Deterministic smoke data for Fineract m_loan_installment_delinquency_tag
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_loan_installment_delinquency_tag;

INSERT INTO retail_banking_dm.ods_fineract_m_loan_installment_delinquency_tag (
    `id`,
    `delinquency_range_id`,
    `loan_id`,
    `installment_id`,
    `addedon_date`,
    `first_overdue_date`,
    `outstanding_amount`,
    `liftedon_date`,
    `created_by`,
    `version`,
    `last_modified_by`,
    `created_on_utc`,
    `last_modified_on_utc`,
    `load_time`
) VALUES
    (
        1,
        1,
        1,
        1,
        '2025-01-15',
        '2025-01-15',
        100.000000,
        '2025-01-15',
        1,
        1,
        1,
        '2025-01-15 09:00:00',
        '2025-01-15 09:00:00',
        '2025-01-15 00:00:00'
    );
