-- Deterministic smoke data for Fineract acc_gl_financial_activity_account
TRUNCATE TABLE retail_banking_dm.ods_fineract_acc_gl_financial_activity_account;

INSERT INTO retail_banking_dm.ods_fineract_acc_gl_financial_activity_account (
    `id`,
    `gl_account_id`,
    `financial_activity_type`,
    `load_time`
) VALUES
    (
        1,
        1,
        1,
        '2025-01-15 00:00:00'
    );
