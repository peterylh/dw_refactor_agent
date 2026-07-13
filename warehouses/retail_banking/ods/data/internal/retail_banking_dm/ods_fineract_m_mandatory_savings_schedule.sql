-- Deterministic smoke data for Fineract m_mandatory_savings_schedule
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_mandatory_savings_schedule;

INSERT INTO retail_banking_dm.ods_fineract_m_mandatory_savings_schedule (
    `id`,
    `savings_account_id`,
    `fromdate`,
    `duedate`,
    `installment`,
    `deposit_amount`,
    `deposit_amount_completed_derived`,
    `total_paid_in_advance_derived`,
    `total_paid_late_derived`,
    `completed_derived`,
    `obligations_met_on_date`,
    `created_by`,
    `created_date`,
    `lastmodified_date`,
    `last_modified_by`,
    `created_on_utc`,
    `last_modified_on_utc`,
    `load_time`
) VALUES
    (
        1,
        1,
        '2025-01-15',
        '2025-01-15',
        1,
        100.000000,
        100.000000,
        1,
        1,
        FALSE,
        '2025-01-15',
        1,
        '2025-01-15 09:00:00',
        '2025-01-15 09:00:00',
        1,
        '2025-01-15 09:00:00',
        '2025-01-15 09:00:00',
        '2025-01-15 00:00:00'
    );
