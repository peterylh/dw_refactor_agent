-- Deterministic smoke data for Fineract m_group
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_group;

INSERT INTO retail_banking_dm.ods_fineract_m_group (
    `id`,
    `external_id`,
    `status_enum`,
    `activation_date`,
    `office_id`,
    `staff_id`,
    `parent_id`,
    `level_id`,
    `display_name`,
    `hierarchy`,
    `closure_reason_cv_id`,
    `closedon_date`,
    `activatedon_userid`,
    `submittedon_date`,
    `submittedon_userid`,
    `closedon_userid`,
    `account_no`,
    `load_time`
) VALUES
    (
        1,
        '00000000-0000-4000-8000-000000000001',
        1,
        '2025-01-15',
        1,
        1,
        1,
        1,
        'Synthetic m_group 1',
        'm_group_hierarchy_1',
        1,
        '2025-01-15',
        1,
        '2025-01-15',
        1,
        1,
        'A000000001',
        '2025-01-15 00:00:00'
    );
