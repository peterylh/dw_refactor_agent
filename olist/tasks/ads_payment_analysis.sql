-- ============================================================
-- 加工作业: ADS 支付方式分析表
-- 源表: dwd_order_detail
-- 加工逻辑: 按月+支付方式汇总 -> 计算占比 -> 修正异常
-- 说明: 从 DWD 层读取，避免直接依赖 ODS
-- ============================================================

-- Step 1: 清空目标表
TRUNCATE TABLE olist_dm.ads_payment_analysis;

-- Step 2: 按月支付方式汇总
INSERT INTO olist_dm.ads_payment_analysis
WITH payment_monthly AS (
    SELECT
        order_month AS stat_month,
        payment_type,
        COUNT(*) AS transaction_count,
        ROUND(SUM(price + freight_value), 2) AS total_value,
        ROUND(AVG(payment_installments), 2) AS avg_installments
    FROM olist_dm.dwd_order_detail
    WHERE payment_type IS NOT NULL
    GROUP BY order_month, payment_type
),
monthly_totals AS (
    SELECT
        stat_month,
        ROUND(SUM(total_value), 2) AS grand_total
    FROM payment_monthly
    GROUP BY stat_month
)
SELECT
    pm.stat_month,
    pm.payment_type,
    pm.transaction_count,
    pm.total_value,
    pm.avg_installments,
    ROUND(pm.total_value / NULLIF(mt.grand_total, 0) * 100, 2) AS payment_pct,
    NOW() AS etl_time
FROM payment_monthly pm
LEFT JOIN monthly_totals mt ON pm.stat_month = mt.stat_month;

-- Step 3: 占比空值修正 0
UPDATE olist_dm.ads_payment_analysis
SET payment_pct = 0.00
WHERE payment_pct IS NULL;

-- Step 4: 删除支付金额为 0 记录
DELETE FROM olist_dm.ads_payment_analysis
WHERE total_value = 0;
