-- Deterministic smoke data for Fineract m_loanproduct_provisioning_mapping
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_loanproduct_provisioning_mapping;

INSERT INTO retail_banking_dm.ods_fineract_m_loanproduct_provisioning_mapping (
    `id`,
    `product_id`,
    `criteria_id`,
    `load_time`
) VALUES
    (
        1,
        1,
        1,
        '2025-01-15 00:00:00'
    );
