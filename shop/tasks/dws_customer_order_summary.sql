-- ============================================================
-- 加工作业: DWS 客户订单汇总表
-- 源表: dwd_order_detail
-- 加工逻辑: 按客户+日期汇总 -> 修正异常值 -> 剔除无效记录
-- 写入模式: 全量刷新,按 stat_date 分区
-- ============================================================

-- Step 1: 清空目标表
TRUNCATE TABLE shop_dm.dws_customer_order_summary;

-- Step 2: 按客户+日期汇总订单指标
INSERT INTO shop_dm.dws_customer_order_summary
SELECT
    customer_id,
    order_date AS stat_date,
    COUNT(DISTINCT order_id) AS order_count,
    SUM(subtotal) AS total_amount,
    SUM(discount) AS total_discount,
    SUM(subtotal - discount) AS payment_amount,
    ROUND(SUM(subtotal) / NULLIF(COUNT(DISTINCT order_id), 0), 2) AS avg_order_amount,
    NOW() AS etl_time
FROM shop_dm.dwd_order_detail
GROUP BY customer_id, order_date;

-- Step 3: 平均客单价为空时修正为 0
UPDATE shop_dm.dws_customer_order_summary
SET avg_order_amount = 0.00
WHERE avg_order_amount IS NULL;

-- Step 4: 删除实付金额为负数的异常记录（保留 0 值记录，如全额折扣订单）
DELETE FROM shop_dm.dws_customer_order_summary
WHERE payment_amount < 0;
