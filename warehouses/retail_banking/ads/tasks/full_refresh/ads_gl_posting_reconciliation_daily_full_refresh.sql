SET @etl_end_date = COALESCE(@etl_end_date, CURDATE());
SET @etl_start_date = COALESCE(@etl_start_date, @etl_end_date);

-- Reviewed application metrics derived from retail_banking_dm.dws_gl_journal_posting_daily
TRUNCATE TABLE retail_banking_dm.ads_gl_posting_reconciliation_daily;

INSERT INTO retail_banking_dm.ads_gl_posting_reconciliation_daily (
    `stat_date`,
    `transaction_id`,
    `office_id`,
    `currency_code`,
    `debit_amount`,
    `credit_amount`,
    `imbalance_amount`,
    `is_balanced`,
    `etl_time`
)
SELECT
    src.`stat_date`,
    src.`transaction_id`,
    src.`office_id`,
    src.`currency_code`,
    sum(case when src.`type_enum` = 1 then src.`total_amount` else 0 end) AS `debit_amount`,
    sum(case when src.`type_enum` = 2 then src.`total_amount` else 0 end) AS `credit_amount`,
    (sum(case when src.`type_enum` = 1 then src.`total_amount` else 0 end)) - (sum(case when src.`type_enum` = 2 then src.`total_amount` else 0 end)) AS `imbalance_amount`,
    abs(((sum(case when src.`type_enum` = 1 then src.`total_amount` else 0 end)) - (sum(case when src.`type_enum` = 2 then src.`total_amount` else 0 end)))) <= 0.000001 AS `is_balanced`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.dws_gl_journal_posting_daily AS src
WHERE (src.`stat_date` IS NULL OR (src.`stat_date` >= CAST(@etl_start_date AS DATE) AND src.`stat_date` <= CAST(@etl_end_date AS DATE)))
GROUP BY
    src.`stat_date`,
    src.`transaction_id`,
    src.`office_id`,
    src.`currency_code`;
