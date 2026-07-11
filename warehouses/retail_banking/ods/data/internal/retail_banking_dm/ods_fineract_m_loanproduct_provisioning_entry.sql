-- Deterministic smoke data for Fineract m_loanproduct_provisioning_entry
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_loanproduct_provisioning_entry;

INSERT INTO retail_banking_dm.ods_fineract_m_loanproduct_provisioning_entry (
    `id`,
    `history_id`,
    `criteria_id`,
    `currency_code`,
    `office_id`,
    `product_id`,
    `category_id`,
    `overdue_in_days`,
    `reseve_amount`,
    `liability_account`,
    `expense_account`,
    `load_time`
) VALUES
    (
        1,
        1,
        1,
        'USD',
        1,
        1,
        1,
        1,
        100.000000,
        1,
        1,
        '2025-01-15 00:00:00'
    );
