-- Deterministic smoke data for Fineract m_payment_detail
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_payment_detail;

INSERT INTO retail_banking_dm.ods_fineract_m_payment_detail (
    `id`,
    `payment_type_id`,
    `account_number`,
    `check_number`,
    `receipt_number`,
    `bank_number`,
    `routing_code`,
    `load_time`
) VALUES
    (
        1,
        1,
        'A000000001',
        'm_payment_detail_check_number_1',
        'm_payment_detail_receipt_number_1',
        'm_payment_detail_bank_number_1',
        'm_payment_detail_routing_code_1',
        '2025-01-15 00:00:00'
    );
