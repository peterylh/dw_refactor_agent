-- Deterministic smoke data for Fineract m_product_loan_guarantee_details
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_product_loan_guarantee_details;

INSERT INTO retail_banking_dm.ods_fineract_m_product_loan_guarantee_details (
    `id`,
    `loan_product_id`,
    `mandatory_guarantee`,
    `minimum_guarantee_from_own_funds`,
    `minimum_guarantee_from_guarantor_funds`,
    `load_time`
) VALUES
    (
        1,
        1,
        1,
        1,
        1,
        '2025-01-15 00:00:00'
    );
