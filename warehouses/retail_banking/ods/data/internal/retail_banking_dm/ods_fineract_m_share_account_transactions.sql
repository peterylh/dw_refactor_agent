-- Deterministic smoke data for Fineract m_share_account_transactions
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_share_account_transactions;

INSERT INTO retail_banking_dm.ods_fineract_m_share_account_transactions (
    `id`,
    `account_id`,
    `transaction_date`,
    `total_shares`,
    `unit_price`,
    `amount`,
    `charge_amount`,
    `amount_paid`,
    `status_enum`,
    `type_enum`,
    `is_active`,
    `load_time`
) VALUES
    (
        1,
        1,
        '2025-01-15',
        1,
        1,
        100.000000,
        100.000000,
        100.000000,
        1,
        1,
        FALSE,
        '2025-01-15 00:00:00'
    ),
    (
        2,
        1,
        '2025-01-16',
        2,
        2,
        100.000000,
        100.000000,
        100.000000,
        1,
        1,
        FALSE,
        '2025-01-15 00:00:00'
    );
