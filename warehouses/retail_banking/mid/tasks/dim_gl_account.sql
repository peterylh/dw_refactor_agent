-- Human-reviewed semantic target: retail_banking_dm.dim_gl_account
TRUNCATE TABLE retail_banking_dm.dim_gl_account;

INSERT INTO retail_banking_dm.dim_gl_account (
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
    `etl_time`
)
SELECT
    src.`id`,
    src.`name`,
    src.`parent_id`,
    src.`hierarchy`,
    src.`gl_code`,
    src.`disabled`,
    src.`manual_journal_entries_allowed`,
    src.`account_usage`,
    src.`classification_enum`,
    src.`tag_id`,
    src.`description`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.ods_fineract_acc_gl_account AS src;
