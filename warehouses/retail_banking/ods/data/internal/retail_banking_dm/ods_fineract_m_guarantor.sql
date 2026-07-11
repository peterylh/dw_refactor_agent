-- Deterministic smoke data for Fineract m_guarantor
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_guarantor;

INSERT INTO retail_banking_dm.ods_fineract_m_guarantor (
    `id`,
    `loan_id`,
    `client_reln_cv_id`,
    `type_enum`,
    `entity_id`,
    `firstname`,
    `lastname`,
    `dob`,
    `address_line_1`,
    `address_line_2`,
    `city`,
    `state`,
    `country`,
    `zip`,
    `house_phone_number`,
    `mobile_number`,
    `comment`,
    `is_active`,
    `load_time`
) VALUES
    (
        1,
        1,
        1,
        1,
        1,
        'Synthetic m_guarantor 1',
        'Synthetic m_guarantor 1',
        '2025-01-15',
        'm_guarantor_address_line_1_1',
        'm_guarantor_address_line_2_1',
        'm_guarantor_city_1',
        'm_guarantor_state_1',
        'US',
        'm_guarantor_zip_1',
        '15500000001',
        '15500000001',
        'm_guarantor_comment_1',
        FALSE,
        '2025-01-15 00:00:00'
    );
