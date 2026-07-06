-- DWD 订单头事实表
SET @etl_date = COALESCE(@etl_date, CURDATE());

DELETE FROM shop_layering_fix_dm.dwd_order
WHERE IF(@full_refresh = 1, 1=1, order_date = CAST(@etl_date AS DATE));

INSERT INTO shop_layering_fix_dm.dwd_order
SELECT
    order_id,
    order_date,
    COUNT(*) AS item_count,
    SUM(subtotal) AS total_amount,
    NOW() AS etl_time
FROM shop_layering_fix_dm.dwd_order_detail
WHERE IF(@full_refresh = 1, 1=1, order_date = CAST(@etl_date AS DATE))
GROUP BY order_id, order_date;
