-- 门店日销售汇总全量窗口作业
SET @etl_start_date = COALESCE(@etl_start_date, @etl_end_date, CURDATE());
SET @etl_end_date = COALESCE(@etl_end_date, @etl_start_date, CURDATE());

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
WHERE order_date BETWEEN CAST(@etl_start_date AS DATE)
    AND CAST(@etl_end_date AS DATE)
GROUP BY store_id, order_date
HAVING COUNT(DISTINCT order_id) <> 0
   AND (
       SUM(subtotal - discount) IS NULL
       OR SUM(subtotal - discount) >= 0
   );

DELETE FROM shop_dm.dws_store_sales_daily
WHERE stat_date BETWEEN CAST(@etl_start_date AS DATE)
    AND CAST(@etl_end_date AS DATE);

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
