-- Deterministic smoke data for Fineract m_portfolio_account_associations
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_portfolio_account_associations;

INSERT INTO retail_banking_dm.ods_fineract_m_portfolio_account_associations (
    `id`,
    `loan_account_id`,
    `savings_account_id`,
    `linked_loan_account_id`,
    `linked_savings_account_id`,
    `association_type_enum`,
    `is_active`,
    `load_time`
) VALUES
    (
        1,
        1,
        1,
        1,
        1,
        1,
        FALSE,
        '2025-01-15 00:00:00'
    );
