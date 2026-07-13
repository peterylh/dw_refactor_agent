-- Deterministic smoke data for Fineract m_loan_capitalized_income_balance
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_loan_capitalized_income_balance;

INSERT INTO retail_banking_dm.ods_fineract_m_loan_capitalized_income_balance (
    `id`,
    `version`,
    `loan_id`,
    `loan_transaction_id`,
    `amount`,
    `date`,
    `unrecognized_amount`,
    `charged_off_amount`,
    `amount_adjustment`,
    `created_by`,
    `created_on_utc`,
    `last_modified_by`,
    `last_modified_on_utc`,
    `is_deleted`,
    `is_closed`,
    `load_time`
) VALUES
    (
        1,
        1,
        1,
        1,
        100.000000,
        '2025-01-15',
        100.000000,
        100.000000,
        100.000000,
        1,
        '2025-01-15 09:00:00',
        1,
        '2025-01-15 09:00:00',
        FALSE,
        FALSE,
        '2025-01-15 00:00:00'
    );
