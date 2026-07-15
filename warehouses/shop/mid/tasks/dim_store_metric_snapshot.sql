-- Anti-pattern fixture: DIM table carries a metric field.
SET @etl_date = COALESCE(@etl_date, CURDATE());

DELETE FROM shop_dm.dim_store_metric_snapshot
WHERE IF(@full_refresh = 1, 1=1, snapshot_date = CAST(@etl_date AS DATE));

INSERT INTO shop_dm.dim_store_metric_snapshot
SELECT
    s.store_id,
    s.snapshot_date,
    s.store_name,
    COALESCE(ss.order_count, 0) AS store_order_count,
    NOW() AS etl_time
FROM shop_dm.dwd_store s
LEFT JOIN shop_dm.stage_store_sales_daily ss
    ON s.store_id = ss.store_id
    AND s.snapshot_date = ss.stat_date
WHERE IF(@full_refresh = 1, 1=1, s.snapshot_date = CAST(@etl_date AS DATE));
