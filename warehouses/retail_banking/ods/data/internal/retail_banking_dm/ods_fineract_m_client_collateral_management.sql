-- Deterministic smoke data for Fineract m_client_collateral_management
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_client_collateral_management;

INSERT INTO retail_banking_dm.ods_fineract_m_client_collateral_management (
    `id`,
    `quantity`,
    `client_id`,
    `collateral_id`,
    `load_time`
) VALUES
    (
        1,
        1,
        1,
        1,
        '2025-01-15 00:00:00'
    );
