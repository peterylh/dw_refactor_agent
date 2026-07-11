-- Deterministic smoke data for Fineract m_deposit_account_on_hold_transaction
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_deposit_account_on_hold_transaction;

INSERT INTO retail_banking_dm.ods_fineract_m_deposit_account_on_hold_transaction (
    `id`,
    `savings_account_id`,
    `amount`,
    `transaction_type_enum`,
    `transaction_date`,
    `is_reversed`,
    `created_date`,
    `created_by`,
    `last_modified_by`,
    `created_on_utc`,
    `last_modified_on_utc`,
    `load_time`
) VALUES
    (
        1,
        1,
        100.000000,
        1,
        '2025-01-15',
        FALSE,
        '2025-01-15 09:00:00',
        1,
        1,
        '2025-01-15 09:00:00',
        '2025-01-15 09:00:00',
        '2025-01-15 00:00:00'
    );
