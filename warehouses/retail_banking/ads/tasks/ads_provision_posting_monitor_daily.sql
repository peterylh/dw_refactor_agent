-- Reviewed application metrics derived from retail_banking_dm.dws_loan_provision_run_daily
TRUNCATE TABLE retail_banking_dm.ads_provision_posting_monitor_daily;

INSERT INTO retail_banking_dm.ads_provision_posting_monitor_daily (
    `stat_date`,
    `office_id`,
    `product_id`,
    `category_id`,
    `currency_code`,
    `provision_entry_count`,
    `total_reserve_amount`,
    `unposted_entry_count`,
    `unposted_reserve_amount`,
    `posting_ratio`,
    `etl_time`
)
SELECT
    src.`stat_date`,
    src.`office_id`,
    src.`product_id`,
    src.`category_id`,
    src.`currency_code`,
    sum(src.`provision_entry_count`) AS `provision_entry_count`,
    sum(src.`total_reserve_amount`) AS `total_reserve_amount`,
    sum(case when coalesce(src.`journal_entry_created`, false) = false then src.`provision_entry_count` else 0 end) AS `unposted_entry_count`,
    sum(case when coalesce(src.`journal_entry_created`, false) = false then src.`total_reserve_amount` else 0 end) AS `unposted_reserve_amount`,
    1 - (sum(case when coalesce(src.`journal_entry_created`, false) = false then src.`provision_entry_count` else 0 end)) / nullif((sum(src.`provision_entry_count`)), 0) AS `posting_ratio`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.dws_loan_provision_run_daily AS src
GROUP BY
    src.`stat_date`,
    src.`office_id`,
    src.`product_id`,
    src.`category_id`,
    src.`currency_code`;
