-- Deterministic smoke data for Fineract ref_loan_transaction_processing_strategy
TRUNCATE TABLE retail_banking_dm.ods_fineract_ref_loan_transaction_processing_strategy;

INSERT INTO retail_banking_dm.ods_fineract_ref_loan_transaction_processing_strategy (
    `id`,
    `code`,
    `name`,
    `sort_order`,
    `load_time`
) VALUES
    (
        1,
        'ref_loan_transaction_processing_strategy_code_1',
        'Synthetic ref_loan_transaction_processing_strategy 1',
        1,
        '2025-01-15 00:00:00'
    );
