-- Deterministic smoke data for Fineract m_loan_interest_recalculation_additional_details
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_loan_interest_recalculation_additional_details;

INSERT INTO retail_banking_dm.ods_fineract_m_loan_interest_recalculation_additional_details (
    `id`,
    `loan_repayment_schedule_id`,
    `effective_date`,
    `amount`,
    `load_time`
) VALUES
    (
        1,
        1,
        '2025-01-15',
        100.000000,
        '2025-01-15 00:00:00'
    );
