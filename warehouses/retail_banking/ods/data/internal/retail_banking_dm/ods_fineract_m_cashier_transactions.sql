-- Deterministic smoke data for Fineract m_cashier_transactions
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_cashier_transactions;

INSERT INTO retail_banking_dm.ods_fineract_m_cashier_transactions (
    `id`,
    `cashier_id`,
    `txn_type`,
    `txn_amount`,
    `txn_date`,
    `created_date`,
    `entity_type`,
    `entity_id`,
    `txn_note`,
    `currency_code`,
    `load_time`
) VALUES
    (
        1,
        1,
        1,
        100.000000,
        '2025-01-15',
        '2025-01-15 09:00:00',
        'm_cashier_transactions_entity_type_1',
        1,
        'm_cashier_transactions_txn_note_1',
        'USD',
        '2025-01-15 00:00:00'
    ),
    (
        2,
        1,
        2,
        100.000000,
        '2025-01-16',
        '2025-01-16 09:00:00',
        'm_cashier_transactions_entity_type_2',
        1,
        'm_cashier_transactions_txn_note_2',
        'USD',
        '2025-01-15 00:00:00'
    );
