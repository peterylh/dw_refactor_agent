-- Deterministic smoke data for Fineract m_wc_loan_balance
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_wc_loan_balance;

INSERT INTO retail_banking_dm.ods_fineract_m_wc_loan_balance (
    `id`,
    `wc_loan_id`,
    `principal_paid`,
    `realized_income_from_discount_fee`,
    `version`,
    `created_by`,
    `last_modified_by`,
    `created_on_utc`,
    `last_modified_on_utc`,
    `overpayment_amount`,
    `principal`,
    `fee`,
    `fee_paid`,
    `penalty`,
    `penalty_paid`,
    `total_disbursement`,
    `total_discount_fee`,
    `total_discount_fee_adjustment`,
    `load_time`
) VALUES
    (
        1,
        1,
        100.000000,
        100.000000,
        1,
        1,
        1,
        '2025-01-15 09:00:00',
        '2025-01-15 09:00:00',
        100.000000,
        100.000000,
        100.000000,
        100.000000,
        100.000000,
        100.000000,
        1,
        100.000000,
        100.000000,
        '2025-01-15 00:00:00'
    );
