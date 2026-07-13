-- Human-reviewed semantic target: retail_banking_dm.dim_teller
TRUNCATE TABLE retail_banking_dm.dim_teller;

INSERT INTO retail_banking_dm.dim_teller (
    `id`,
    `office_id`,
    `debit_account_id`,
    `credit_account_id`,
    `name`,
    `description`,
    `valid_from`,
    `valid_to`,
    `state`,
    `etl_time`
)
SELECT
    src.`id`,
    src.`office_id`,
    src.`debit_account_id`,
    src.`credit_account_id`,
    src.`name`,
    src.`description`,
    src.`valid_from`,
    src.`valid_to`,
    src.`state`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.ods_fineract_m_tellers AS src;
