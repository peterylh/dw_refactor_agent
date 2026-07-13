-- Reviewed application metrics derived from retail_banking_dm.dws_loan_transaction_daily
TRUNCATE TABLE retail_banking_dm.ads_loan_transaction_kpi_daily;

INSERT INTO retail_banking_dm.ads_loan_transaction_kpi_daily (
    `stat_date`,
    `office_id`,
    `loan_id`,
    `transaction_type_enum`,
    `record_count`,
    `total_amount`,
    `average_amount`,
    `principal_component_ratio`,
    `interest_component_ratio`,
    `etl_time`
)
SELECT
    src.`stat_date`,
    src.`office_id`,
    src.`loan_id`,
    src.`transaction_type_enum`,
    src.`record_count` AS `record_count`,
    src.`total_amount` AS `total_amount`,
    (src.`total_amount`) / nullif((src.`record_count`), 0) AS `average_amount`,
    src.`total_principal_component` / nullif((src.`total_amount`), 0) AS `principal_component_ratio`,
    src.`total_interest_component` / nullif((src.`total_amount`), 0) AS `interest_component_ratio`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.dws_loan_transaction_daily AS src;
