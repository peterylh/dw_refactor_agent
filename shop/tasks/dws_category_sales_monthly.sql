-- ============================================================
-- 加工作业: DWS 品类月度销售汇总表
-- 源表: dwd_order_detail
-- 加工逻辑: 按品类+月份汇总 -> 清理空值 -> 剔除无效数据
-- ============================================================

-- Step 1: 清空目标表
TRUNCATE TABLE shop_dm.dws_category_sales_monthly;

-- Step 2: 按品类+月份汇总销售指标
INSERT INTO shop_dm.dws_category_sales_monthly
SELECT
    category_id,
    order_month AS stat_month,
    COUNT(DISTINCT order_id) AS order_count,
    SUM(quantity) AS sale_quantity,
    SUM(subtotal) AS sale_amount,
    NOW() AS etl_time
FROM shop_dm.dwd_order_detail
WHERE category_id IS NOT NULL
GROUP BY category_id, order_month;

-- Step 3: 销售数量为空时修正为 0
UPDATE shop_dm.dws_category_sales_monthly
SET sale_quantity = 0
WHERE sale_quantity IS NULL;

-- Step 4: 删除销售额为 0 的记录
DELETE FROM shop_dm.dws_category_sales_monthly
WHERE sale_amount = 0;
