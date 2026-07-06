-- DWS 门店日指标快照表
SET @etl_date = COALESCE(@etl_date, CURDATE());

DELETE FROM shop_layering_fix_dm.dws_store_metric_snapshot_daily
WHERE IF(@full_refresh = 1, 1=1, stat_date = CAST(@etl_date AS DATE));

INSERT INTO shop_layering_fix_dm.dws_store_metric_snapshot_daily
SELECT
    s.store_id,
    s.snapshot_date AS stat_date,
    s.store_name,
    COALESCE(ssd.order_count, 0) AS store_order_count,
    NOW() AS etl_time
FROM shop_layering_fix_dm.dim_store s
LEFT JOIN shop_layering_fix_dm.dws_store_sales_daily ssd
    ON s.store_id = ssd.store_id
    AND s.snapshot_date = ssd.stat_date
    AND IF(@full_refresh = 1, 1=1, ssd.stat_date = CAST(@etl_date AS DATE))
WHERE IF(@full_refresh = 1, 1=1, s.snapshot_date = CAST(@etl_date AS DATE));
