-- Deterministic smoke data for Fineract m_loan_collateral_management
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_loan_collateral_management;

INSERT INTO retail_banking_dm.ods_fineract_m_loan_collateral_management (
    `id`,
    `quantity`,
    `loan_id`,
    `client_collateral_id`,
    `is_released`,
    `transaction_id`,
    `load_time`
) VALUES
    (
        1,
        1,
        1,
        1,
        FALSE,
        1,
        '2025-01-15 00:00:00'
    );
