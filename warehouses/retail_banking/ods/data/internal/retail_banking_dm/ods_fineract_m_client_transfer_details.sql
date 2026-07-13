-- Deterministic smoke data for Fineract m_client_transfer_details
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_client_transfer_details;

INSERT INTO retail_banking_dm.ods_fineract_m_client_transfer_details (
    `id`,
    `client_id`,
    `from_office_id`,
    `to_office_id`,
    `proposed_transfer_date`,
    `transfer_type`,
    `submitted_on`,
    `submitted_by`,
    `load_time`
) VALUES
    (
        1,
        1,
        1,
        1,
        '2025-01-15',
        1,
        '2025-01-15',
        1,
        '2025-01-15 00:00:00'
    );
