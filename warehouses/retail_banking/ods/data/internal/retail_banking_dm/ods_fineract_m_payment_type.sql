-- Deterministic smoke data for Fineract m_payment_type
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_payment_type;

INSERT INTO retail_banking_dm.ods_fineract_m_payment_type (
    `id`,
    `value`,
    `description`,
    `is_cash_payment`,
    `order_position`,
    `code_name`,
    `is_system_defined`,
    `load_time`
) VALUES
    (
        1,
        'm_payment_type_value_1',
        'm_payment_type_description_1',
        FALSE,
        1,
        'm_payment_type_code_name_1',
        FALSE,
        '2025-01-15 00:00:00'
    );
