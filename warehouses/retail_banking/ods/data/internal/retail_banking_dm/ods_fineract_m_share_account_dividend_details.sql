-- Deterministic smoke data for Fineract m_share_account_dividend_details
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_share_account_dividend_details;

INSERT INTO retail_banking_dm.ods_fineract_m_share_account_dividend_details (
    `id`,
    `dividend_pay_out_id`,
    `account_id`,
    `amount`,
    `status`,
    `savings_transaction_id`,
    `load_time`
) VALUES
    (
        1,
        1,
        1,
        100.000000,
        300,
        1,
        '2025-01-15 00:00:00'
    );
