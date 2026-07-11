-- Deterministic smoke data for Fineract m_loan_repayment_schedule_history
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_loan_repayment_schedule_history;

INSERT INTO retail_banking_dm.ods_fineract_m_loan_repayment_schedule_history (
    `id`,
    `loan_id`,
    `loan_reschedule_request_id`,
    `fromdate`,
    `duedate`,
    `installment`,
    `principal_amount`,
    `interest_amount`,
    `fee_charges_amount`,
    `penalty_charges_amount`,
    `createdby_id`,
    `created_date`,
    `lastmodified_date`,
    `lastmodifiedby_id`,
    `version`,
    `created_on_utc`,
    `last_modified_on_utc`,
    `load_time`
) VALUES
    (
        1,
        1,
        1,
        '2025-01-15',
        '2025-01-15',
        1,
        100.000000,
        100.000000,
        100.000000,
        100.000000,
        1,
        '2025-01-15 09:00:00',
        '2025-01-15 09:00:00',
        1,
        1,
        '2025-01-15 09:00:00',
        '2025-01-15 09:00:00',
        '2025-01-15 00:00:00'
    );
