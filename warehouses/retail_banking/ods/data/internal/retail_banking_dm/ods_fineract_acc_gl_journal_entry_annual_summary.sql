-- Deterministic smoke data for Fineract acc_gl_journal_entry_annual_summary
TRUNCATE TABLE retail_banking_dm.ods_fineract_acc_gl_journal_entry_annual_summary;

INSERT INTO retail_banking_dm.ods_fineract_acc_gl_journal_entry_annual_summary (
    `id`,
    `gl_code`,
    `product_id`,
    `office_id`,
    `opening_balance_amount`,
    `currency_code`,
    `owner_external_id`,
    `manual_entry`,
    `year_end_date`,
    `created_by`,
    `created_on_utc`,
    `last_modified_by`,
    `last_modified_on_utc`,
    `originator_external_ids`,
    `load_time`
) VALUES
    (
        1,
        'acc_gl_journal_entry_annual_summary_gl_code_1',
        1,
        1,
        100.000000,
        'USD',
        '00000000-0000-4000-8000-000000000001',
        FALSE,
        '2025-01-15',
        1,
        '2025-01-15 09:00:00',
        1,
        '2025-01-15 09:00:00',
        '00000000-0000-4000-8000-000000000001',
        '2025-01-15 00:00:00'
    );
