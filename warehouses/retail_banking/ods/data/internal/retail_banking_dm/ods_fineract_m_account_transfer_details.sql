-- Deterministic smoke data for Fineract m_account_transfer_details
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_account_transfer_details;

INSERT INTO retail_banking_dm.ods_fineract_m_account_transfer_details (
    `id`,
    `from_office_id`,
    `to_office_id`,
    `from_client_id`,
    `to_client_id`,
    `from_savings_account_id`,
    `to_savings_account_id`,
    `from_loan_account_id`,
    `to_loan_account_id`,
    `transfer_type`,
    `load_time`
) VALUES
    (
        1,
        1,
        1,
        1,
        1,
        1,
        1,
        1,
        1,
        1,
        '2025-01-15 00:00:00'
    );
