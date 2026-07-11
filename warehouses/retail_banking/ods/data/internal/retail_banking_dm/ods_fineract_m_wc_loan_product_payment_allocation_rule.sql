-- Deterministic smoke data for Fineract m_wc_loan_product_payment_allocation_rule
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_wc_loan_product_payment_allocation_rule;

INSERT INTO retail_banking_dm.ods_fineract_m_wc_loan_product_payment_allocation_rule (
    `id`,
    `wc_loan_product_id`,
    `transaction_type`,
    `allocation_types`,
    `created_by`,
    `last_modified_by`,
    `created_on_utc`,
    `last_modified_on_utc`,
    `load_time`
) VALUES
    (
        1,
        1,
        'm_wc_loan_product_payment_allocation_rule_transaction_type_1',
        'm_wc_loan_product_payment_allocation_rule_allocation_types_1',
        1,
        1,
        '2025-01-15 09:00:00',
        '2025-01-15 09:00:00',
        '2025-01-15 00:00:00'
    );
