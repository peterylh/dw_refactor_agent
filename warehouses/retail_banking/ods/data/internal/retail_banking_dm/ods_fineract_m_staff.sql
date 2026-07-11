-- Deterministic smoke data for Fineract m_staff
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_staff;

INSERT INTO retail_banking_dm.ods_fineract_m_staff (
    `id`,
    `is_loan_officer`,
    `office_id`,
    `firstname`,
    `lastname`,
    `display_name`,
    `mobile_no`,
    `external_id`,
    `organisational_role_enum`,
    `organisational_role_parent_staff_id`,
    `is_active`,
    `joining_date`,
    `image_id`,
    `email_address`,
    `load_time`
) VALUES
    (
        1,
        FALSE,
        1,
        'Synthetic m_staff 1',
        'Synthetic m_staff 1',
        'Synthetic m_staff 1',
        '15500000001',
        '00000000-0000-4000-8000-000000000001',
        1,
        1,
        FALSE,
        '2025-01-15',
        1,
        'user1@example.com',
        '2025-01-15 00:00:00'
    );
