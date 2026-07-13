-- Deterministic smoke data for Fineract m_loan_collateral
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_loan_collateral;

INSERT INTO retail_banking_dm.ods_fineract_m_loan_collateral (
    `id`,
    `loan_id`,
    `type_cv_id`,
    `value`,
    `description`,
    `load_time`
) VALUES
    (
        1,
        1,
        1,
        1,
        'm_loan_collateral_description_1',
        '2025-01-15 00:00:00'
    );
