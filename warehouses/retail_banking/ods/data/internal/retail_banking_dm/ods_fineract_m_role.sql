-- Deterministic smoke data for Fineract m_role
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_role;

INSERT INTO retail_banking_dm.ods_fineract_m_role (
    `id`,
    `name`,
    `description`,
    `is_disabled`,
    `load_time`
) VALUES
    (
        1,
        'Synthetic m_role 1',
        'm_role_description_1',
        FALSE,
        '2025-01-15 00:00:00'
    );
