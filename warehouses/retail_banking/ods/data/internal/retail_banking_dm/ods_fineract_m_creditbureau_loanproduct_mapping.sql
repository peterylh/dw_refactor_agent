-- Deterministic smoke data for Fineract m_creditbureau_loanproduct_mapping
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_creditbureau_loanproduct_mapping;

INSERT INTO retail_banking_dm.ods_fineract_m_creditbureau_loanproduct_mapping (
    `id`,
    `organisation_creditbureau_id`,
    `loan_product_id`,
    `is_creditcheck_mandatory`,
    `skip_creditcheck_in_failure`,
    `stale_period`,
    `is_active`,
    `load_time`
) VALUES
    (
        1,
        1,
        1,
        FALSE,
        FALSE,
        1,
        FALSE,
        '2025-01-15 00:00:00'
    );
