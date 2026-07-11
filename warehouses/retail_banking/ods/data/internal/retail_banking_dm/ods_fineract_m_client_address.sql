-- Deterministic smoke data for Fineract m_client_address
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_client_address;

INSERT INTO retail_banking_dm.ods_fineract_m_client_address (
    `id`,
    `client_id`,
    `address_id`,
    `address_type_id`,
    `is_active`,
    `load_time`
) VALUES
    (
        1,
        1,
        1,
        1,
        FALSE,
        '2025-01-15 00:00:00'
    );
