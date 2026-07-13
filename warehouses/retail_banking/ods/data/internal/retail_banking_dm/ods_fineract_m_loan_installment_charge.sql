-- Deterministic smoke data for Fineract m_loan_installment_charge
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_loan_installment_charge;

INSERT INTO retail_banking_dm.ods_fineract_m_loan_installment_charge (
    `id`,
    `loan_charge_id`,
    `loan_schedule_id`,
    `due_date`,
    `amount`,
    `amount_paid_derived`,
    `amount_waived_derived`,
    `amount_writtenoff_derived`,
    `amount_outstanding_derived`,
    `is_paid_derived`,
    `waived`,
    `amount_through_charge_payment`,
    `load_time`
) VALUES
    (
        1,
        1,
        1,
        '2025-01-15',
        100.000000,
        100.000000,
        100.000000,
        100.000000,
        100.000000,
        FALSE,
        FALSE,
        100.000000,
        '2025-01-15 00:00:00'
    );
