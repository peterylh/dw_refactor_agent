-- Deterministic smoke data for Fineract m_wc_loan_transaction_relation
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_wc_loan_transaction_relation;

INSERT INTO retail_banking_dm.ods_fineract_m_wc_loan_transaction_relation (
    `id`,
    `created_by`,
    `last_modified_by`,
    `from_loan_transaction_id`,
    `to_loan_transaction_id`,
    `relation_type_enum`,
    `created_on_utc`,
    `last_modified_on_utc`,
    `to_loan_charge_id`,
    `load_time`
) VALUES
    (
        1,
        1,
        1,
        1,
        1,
        1,
        '2025-01-15 09:00:00',
        '2025-01-15 09:00:00',
        1,
        '2025-01-15 00:00:00'
    );
