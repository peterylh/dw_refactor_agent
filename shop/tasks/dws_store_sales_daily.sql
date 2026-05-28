-- ============================================================
-- 加工作业: DWS 门店日销售汇总表
-- 源表: dwd_order_detail
-- 加工逻辑: 按门店+日期汇总 -> 清理空值 -> 剔除异常数据
-- 写入模式: 按 stat_date 分区, DELETE + INSERT 按日处理
-- ============================================================

SET @etl_date = COALESCE(@etl_date, CURDATE());
-- Step 1: 删除当前统计日期的数据
DELETE FROM shop_dm.dws_store_sales_daily WHERE stat_date = CAST(@etl_date AS DATE);

-- Step 2: 按门店+日期汇总销售指标
INSERT INTO shop_dm.dws_store_sales_daily
SELECT
    store_id,
    order_date AS stat_date,
    COUNT(DISTINCT order_id) AS order_count,
    COUNT(DISTINCT customer_id) AS customer_count,
    SUM(subtotal) AS total_amount,
    SUM(discount) AS discount_amount,
    SUM(subtotal - discount) AS payment_amount,
    NOW() AS etl_time
FROM shop_dm.dwd_order_detail
WHERE order_date = CAST(@etl_date AS DATE)
GROUP BY store_id, order_date;

-- Step 3: 折扣金额为空时修正为 0
UPDATE shop_dm.dws_store_sales_daily
SET discount_amount = 0.00
WHERE discount_amount IS NULL
  AND stat_date = CAST(@etl_date AS DATE);

-- Step 4: 删除订单数为 0 的记录
DELETE FROM shop_dm.dws_store_sales_daily
WHERE order_count = 0
  AND stat_date = CAST(@etl_date AS DATE);

-- Step 5: 删除实付金额为负数的异常记录
DELETE FROM shop_dm.dws_store_sales_daily
WHERE payment_amount < 0
  AND stat_date = CAST(@etl_date AS DATE);
