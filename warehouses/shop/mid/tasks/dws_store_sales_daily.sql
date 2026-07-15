-- ============================================================
-- 加工作业: DWS 门店日销售汇总表
-- 源表: dwd_order_detail
-- 加工逻辑: 按门店+日期汇总到过程表 -> 清理异常数据 -> 写入目标表
-- 写入模式: 按 stat_date 分区, DELETE + INSERT 按日处理
-- ============================================================

SET @etl_date = COALESCE(@etl_date, CURDATE());
DROP TABLE IF EXISTS shop_dm.stage_store_sales_daily;

CREATE TABLE shop_dm.stage_store_sales_daily
PROPERTIES ("replication_num" = "1")
AS
SELECT
    store_id,
    order_date AS stat_date,
    COUNT(DISTINCT order_id) AS order_count,
    COUNT(DISTINCT customer_id) AS customer_count,
    SUM(subtotal) AS total_amount,
    COALESCE(SUM(discount), 0.00) AS discount_amount,
    SUM(subtotal - discount) AS payment_amount,
    NOW() AS etl_time
FROM shop_dm.dwd_order_detail
WHERE IF(@full_refresh = 1, 1 = 1, order_date = CAST(@etl_date AS DATE))
GROUP BY store_id, order_date
HAVING COUNT(DISTINCT order_id) <> 0
   AND (
       SUM(subtotal - discount) IS NULL
       OR SUM(subtotal - discount) >= 0
   );

DELETE FROM shop_dm.dws_store_sales_daily
WHERE IF(@full_refresh = 1, 1 = 1, stat_date = CAST(@etl_date AS DATE));

INSERT INTO shop_dm.dws_store_sales_daily (
    store_id,
    stat_date,
    order_count,
    customer_count,
    total_amount,
    discount_amount,
    payment_amount,
    etl_time
)
SELECT
    store_id,
    stat_date,
    order_count,
    customer_count,
    total_amount,
    discount_amount,
    payment_amount,
    etl_time
FROM shop_dm.stage_store_sales_daily;
