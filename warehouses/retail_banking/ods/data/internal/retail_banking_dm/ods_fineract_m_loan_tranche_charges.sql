-- Deterministic smoke data for Fineract m_loan_tranche_charges
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_loan_tranche_charges;

INSERT INTO retail_banking_dm.ods_fineract_m_loan_tranche_charges (
    `id`,
    `loan_id`,
    `charge_id`,
    `load_time`
) VALUES
    (
        1,
        1,
        1,
        '2025-01-15 00:00:00'
    );
