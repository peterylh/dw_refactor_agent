-- Deterministic smoke data for Fineract m_code_value
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_code_value;

INSERT INTO retail_banking_dm.ods_fineract_m_code_value (
    `id`,
    `code_id`,
    `code_value`,
    `code_description`,
    `order_position`,
    `code_score`,
    `is_active`,
    `is_mandatory`,
    `load_time`
) VALUES
    (
        1,
        1,
        'm_code_value_code_value_1',
        'm_code_value_code_description_1',
        1,
        1,
        FALSE,
        FALSE,
        '2025-01-15 00:00:00'
    );
