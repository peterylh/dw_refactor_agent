-- 门店指标快照全量窗口作业
SET @etl_start_date = COALESCE(@etl_start_date, @etl_end_date, CURDATE());
SET @etl_end_date = COALESCE(@etl_end_date, @etl_start_date, CURDATE());

DELETE FROM shop_dm.dim_store_metric_snapshot
WHERE snapshot_date BETWEEN CAST(@etl_start_date AS DATE)
    AND CAST(@etl_end_date AS DATE);

INSERT INTO shop_dm.dim_store_metric_snapshot
SELECT
    s.store_id,
    s.snapshot_date,
    s.store_name,
    COALESCE(ss.order_count, 0) AS store_order_count,
    NOW() AS etl_time
FROM shop_dm.dwd_store s
LEFT JOIN shop_dm.dws_store_sales_daily ss
    ON s.store_id = ss.store_id
    AND s.snapshot_date = ss.stat_date
WHERE s.snapshot_date BETWEEN CAST(@etl_start_date AS DATE)
    AND CAST(@etl_end_date AS DATE);
