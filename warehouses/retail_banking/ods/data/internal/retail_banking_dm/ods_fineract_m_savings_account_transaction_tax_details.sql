-- Deterministic smoke data for Fineract m_savings_account_transaction_tax_details
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_savings_account_transaction_tax_details;

INSERT INTO retail_banking_dm.ods_fineract_m_savings_account_transaction_tax_details (
    `id`,
    `savings_transaction_id`,
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
