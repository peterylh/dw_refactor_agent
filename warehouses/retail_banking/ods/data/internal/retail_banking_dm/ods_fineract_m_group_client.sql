-- Deterministic smoke data for Fineract m_group_client
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_group_client;

INSERT INTO retail_banking_dm.ods_fineract_m_group_client (
    `group_id`,
    `client_id`,
    `load_time`
) VALUES
    (
        1,
        1,
        '2025-01-15 00:00:00'
    );
