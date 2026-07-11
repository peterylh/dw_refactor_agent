-- Deterministic smoke data for Fineract m_guarantor_transaction
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_guarantor_transaction;

INSERT INTO retail_banking_dm.ods_fineract_m_guarantor_transaction (
    `id`,
    `guarantor_fund_detail_id`,
    `loan_transaction_id`,
    `deposit_on_hold_transaction_id`,
    `is_reversed`,
    `load_time`
) VALUES
    (
        1,
        1,
        1,
        1,
        FALSE,
        '2025-01-15 00:00:00'
    );
