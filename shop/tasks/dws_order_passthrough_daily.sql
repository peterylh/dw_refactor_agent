-- Anti-pattern fixture: DWS fact is a detail passthrough without aggregation.
SET @etl_date = COALESCE(@etl_date, CURDATE());

DELETE FROM shop_dm.dws_order_passthrough_daily
WHERE IF(@full_refresh = 1, 1=1, stat_date = CAST(@etl_date AS DATE));

INSERT INTO shop_dm.dws_order_passthrough_daily
SELECT
    order_item_id,
    order_id,
    order_date AS stat_date,
    store_id,
    product_id,
    subtotal,
    NOW() AS etl_time
FROM shop_dm.dwd_order_detail
WHERE IF(@full_refresh = 1, 1=1, order_date = CAST(@etl_date AS DATE));
