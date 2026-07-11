-- Deterministic smoke data for Fineract m_appuser_role
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_appuser_role;

INSERT INTO retail_banking_dm.ods_fineract_m_appuser_role (
    `appuser_id`,
    `role_id`,
    `load_time`
) VALUES
    (
        1,
        1,
        '2025-01-15 00:00:00'
    );
