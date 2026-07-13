-- Deterministic smoke data for Fineract m_group_roles
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_group_roles;

INSERT INTO retail_banking_dm.ods_fineract_m_group_roles (
    `id`,
    `client_id`,
    `group_id`,
    `role_cv_id`,
    `load_time`
) VALUES
    (
        1,
        1,
        1,
        1,
        '2025-01-15 00:00:00'
    );
