-- ============================================================
-- 加工作业: DWS 品类月度销售汇总表
-- 源表: dwd_order_detail
-- 加工逻辑: 按品类+月份汇总 -> 仅刷新当月分区 -> 清理空值 -> 剔除无效数据
-- 写入模式: 仅刷新当月分区,按 stat_month_date 分区
-- ============================================================

SET @etl_date = COALESCE(@etl_date, CURDATE());
-- Step 1: 删除当月分区数据（保留历史月份）
DELETE FROM shop_dm.dws_category_sales_monthly
WHERE stat_month = DATE_FORMAT(@etl_date, '%Y-%m');

-- Step 2: 按品类+月份汇总当月数据
INSERT INTO shop_dm.dws_category_sales_monthly
SELECT
    category_id,
    order_month AS stat_month,
    DATE_FORMAT(CONCAT(order_month, '-01'), '%Y-%m-%d') AS stat_month_date,
    COUNT(DISTINCT order_id) AS order_count,
    SUM(quantity) AS sale_quantity,
    SUM(subtotal) AS sale_amount,
    NOW() AS etl_time
FROM shop_dm.dwd_order_detail
WHERE category_id IS NOT NULL
  AND order_month = DATE_FORMAT(@etl_date, '%Y-%m')
GROUP BY category_id, order_month;

-- Step 3: 销售数量为空时修正为 0
UPDATE shop_dm.dws_category_sales_monthly
SET sale_quantity = 0
WHERE sale_quantity IS NULL
  AND stat_month = DATE_FORMAT(@etl_date, '%Y-%m');

-- Step 4: 删除销售额为 0 的记录(仅当月)
DELETE FROM shop_dm.dws_category_sales_monthly
WHERE sale_amount = 0
  AND stat_month = DATE_FORMAT(@etl_date, '%Y-%m');
