-- Core retail-banking reconciliation gates.
-- Every query must return zero rows before a generated batch is accepted.

-- Q1: Fineract GL transaction must balance debit(type=1) and credit(type=2).
SELECT
    `entry_date`,
    `transaction_id`,
    `currency_code`,
    SUM(CASE WHEN `type_enum` = 1 THEN `amount` ELSE 0 END) AS debit_amount,
    SUM(CASE WHEN `type_enum` = 2 THEN `amount` ELSE 0 END) AS credit_amount
FROM retail_banking_dm.dwd_gl_journal_entry
WHERE `reversed` = FALSE
GROUP BY `entry_date`, `transaction_id`, `currency_code`
HAVING ABS(
    SUM(CASE WHEN `type_enum` = 1 THEN `amount` ELSE 0 END)
    - SUM(CASE WHEN `type_enum` = 2 THEN `amount` ELSE 0 END)
) > 0.000001;

-- Q2: Every loan transaction must resolve to a reviewed loan dimension.
SELECT txn.`id`, txn.`loan_id`
FROM retail_banking_dm.dwd_loan_transaction AS txn
LEFT JOIN retail_banking_dm.dim_loan_account AS loan
    ON txn.`loan_id` = loan.`id`
WHERE loan.`id` IS NULL;

-- Q3: Every deposit transaction must resolve to a reviewed deposit dimension.
SELECT txn.`id`, txn.`savings_account_id`
FROM retail_banking_dm.dwd_deposit_transaction AS txn
LEFT JOIN retail_banking_dm.dim_deposit_account AS account
    ON txn.`savings_account_id` = account.`id`
WHERE account.`id` IS NULL;

-- Q4: Every journal line must resolve to a GL account dimension.
SELECT journal.`id`, journal.`account_id`
FROM retail_banking_dm.dwd_gl_journal_entry AS journal
LEFT JOIN retail_banking_dm.dim_gl_account AS account
    ON journal.`account_id` = account.`id`
WHERE account.`id` IS NULL;

-- Q5: Reversed loan transactions must not enter the additive DWS aggregate.
SELECT
    dws.`stat_date`,
    dws.`office_id`,
    dws.`loan_id`,
    dws.`transaction_type_enum`
FROM retail_banking_dm.dws_loan_transaction_daily AS dws
LEFT JOIN (
    SELECT
        DATE(`transaction_date`) AS `stat_date`,
        `office_id`,
        `loan_id`,
        `transaction_type_enum`,
        COUNT(*) AS `record_count`,
        SUM(`amount`) AS `total_amount`
    FROM retail_banking_dm.dwd_loan_transaction
    WHERE `is_reversed` = FALSE
    GROUP BY
        `stat_date`, `office_id`, `loan_id`, `transaction_type_enum`
) AS expected
    ON dws.`stat_date` = expected.`stat_date`
   AND dws.`office_id` = expected.`office_id`
   AND dws.`loan_id` = expected.`loan_id`
   AND dws.`transaction_type_enum` = expected.`transaction_type_enum`
WHERE expected.`loan_id` IS NULL
   OR dws.`record_count` <> expected.`record_count`
   OR ABS(dws.`total_amount` - expected.`total_amount`) > 0.000001;
