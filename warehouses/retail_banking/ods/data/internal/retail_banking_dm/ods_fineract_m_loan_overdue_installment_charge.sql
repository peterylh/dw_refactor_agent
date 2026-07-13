-- Deterministic smoke data for Fineract m_loan_overdue_installment_charge
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_loan_overdue_installment_charge;

INSERT INTO retail_banking_dm.ods_fineract_m_loan_overdue_installment_charge (
    `id`,
    `loan_charge_id`,
    `loan_schedule_id`,
    `frequency_number`,
    `load_time`
) VALUES
    (
        1,
        1,
        1,
        1,
        '2025-01-15 00:00:00'
    );
