-- Deterministic smoke data for Fineract m_loan_tranche_disbursement_charge
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_loan_tranche_disbursement_charge;

INSERT INTO retail_banking_dm.ods_fineract_m_loan_tranche_disbursement_charge (
    `id`,
    `loan_charge_id`,
    `disbursement_detail_id`,
    `load_time`
) VALUES
    (
        1,
        1,
        1,
        '2025-01-15 00:00:00'
    );
