-- Deterministic smoke data for Fineract acc_gl_account
TRUNCATE TABLE retail_banking_dm.ods_fineract_acc_gl_account;

INSERT INTO retail_banking_dm.ods_fineract_acc_gl_account (
    `id`,
    `name`,
    `parent_id`,
    `hierarchy`,
    `gl_code`,
    `disabled`,
    `manual_journal_entries_allowed`,
    `account_usage`,
    `classification_enum`,
    `tag_id`,
    `description`,
    `load_time`
) VALUES
    (
        1,
        'Synthetic acc_gl_account 1',
        1,
        'acc_gl_account_hierarchy_1',
        'acc_gl_account_gl_code_1',
        FALSE,
        FALSE,
        1,
        1,
        1,
        'acc_gl_account_description_1',
        '2025-01-15 00:00:00'
    );
