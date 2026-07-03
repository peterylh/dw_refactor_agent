-- Anti-pattern fixture: DWD fact contains GROUP BY and aggregate metrics.
SET @etl_date = COALESCE(@etl_date, CURDATE());

DELETE FROM shop_dm.dwd_order_summary_bad
WHERE IF(@full_refresh = 1, 1=1, order_date = CAST(@etl_date AS DATE));

INSERT INTO shop_dm.dwd_order_summary_bad
SELECT
    oi.order_id,
    MAX(o.order_date) AS order_date,
    COUNT(*) AS item_count,
    SUM(oi.subtotal) AS total_amount,
    NOW() AS etl_time
FROM shop_dm.ods_order_item oi
INNER JOIN shop_dm.ods_order o ON oi.order_id = o.order_id
WHERE IF(@full_refresh = 1, 1=1, o.order_date = CAST(@etl_date AS DATE))
GROUP BY oi.order_id;
