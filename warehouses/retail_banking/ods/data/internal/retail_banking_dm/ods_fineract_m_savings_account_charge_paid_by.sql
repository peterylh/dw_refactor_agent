-- Deterministic smoke data for Fineract m_savings_account_charge_paid_by
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_savings_account_charge_paid_by;

INSERT INTO retail_banking_dm.ods_fineract_m_savings_account_charge_paid_by (
    `id`,
    `savings_account_transaction_id`,
    `savings_account_charge_id`,
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
