-- Deterministic smoke data for Fineract m_office_transaction
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_office_transaction;

INSERT INTO retail_banking_dm.ods_fineract_m_office_transaction (
    `id`,
    `from_office_id`,
    `to_office_id`,
    `currency_code`,
    `currency_digits`,
    `transaction_amount`,
    `transaction_date`,
    `description`,
    `load_time`
) VALUES
    (
        1,
        1,
        1,
        'USD',
        1,
        100.000000,
        '2025-01-15',
        'm_office_transaction_description_1',
        '2025-01-15 00:00:00'
    );
