-- Deterministic smoke data for Fineract m_account_transfer_transaction
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_account_transfer_transaction;

INSERT INTO retail_banking_dm.ods_fineract_m_account_transfer_transaction (
    `id`,
    `account_transfer_details_id`,
    `from_savings_transaction_id`,
    `from_loan_transaction_id`,
    `to_savings_transaction_id`,
    `to_loan_transaction_id`,
    `is_reversed`,
    `transaction_date`,
    `currency_code`,
    `currency_digits`,
    `currency_multiplesof`,
    `amount`,
    `description`,
    `load_time`
) VALUES
    (
        1,
        1,
        1,
        1,
        1,
        1,
        FALSE,
        '2025-01-15',
        'USD',
        1,
        1,
        100.000000,
        'm_account_transfer_transaction_description_1',
        '2025-01-15 00:00:00'
    ),
    (
        2,
        1,
        1,
        1,
        1,
        1,
        FALSE,
        '2025-01-16',
        'USD',
        2,
        2,
        100.000000,
        'm_account_transfer_transaction_description_2',
        '2025-01-15 00:00:00'
    );
