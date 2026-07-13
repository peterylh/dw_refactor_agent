-- Deterministic smoke data for Fineract m_loan_charge_tax_details
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_loan_charge_tax_details;

INSERT INTO retail_banking_dm.ods_fineract_m_loan_charge_tax_details (
    `id`,
    `loan_charge_id`,
    `tax_component_id`,
    `amount`,
    `load_time`
) VALUES
    (
        1,
        1,
        1,
        100.000000,
        '2025-01-15 00:00:00'
    );
