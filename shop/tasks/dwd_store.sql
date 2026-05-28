-- ============================================================
-- 加工作业: DWD 门店维度宽表 (每日快照)
-- 源表: ods_store
-- 加工逻辑: 门店分级 -> 计算开业年限 -> 补全缺失值
-- 写入模式: 追加每日快照,按 snapshot_date 分区
-- ============================================================

SET @etl_date = COALESCE(@etl_date, CURDATE());
-- Step 1: 全量加载 + 门店评级 + 开业年限 + 回填合并
INSERT INTO shop_dm.dwd_store
SELECT
    store_id,
    CAST(@etl_date AS DATE) AS snapshot_date,
    NOW() AS etl_time,
    store_name,
    COALESCE(NULLIF(store_type, ''),
        CASE
            WHEN area_size >= 3000 THEN '旗舰店'
            WHEN area_size >= 1000 THEN '标准店'
            ELSE '社区店'
        END
    ) AS store_type,
    CASE
        WHEN area_size >= 3000 THEN 'A级'
        WHEN area_size >= 1000 THEN 'B级'
        ELSE 'C级'
    END AS store_level,
    address,
    city,
    COALESCE(
        CASE
            WHEN city = '北京' THEN '北京'
            WHEN city = '上海' THEN '上海'
            WHEN city IN ('广州','深圳') THEN '广东'
            WHEN city = '成都' THEN '四川'
            WHEN city = '杭州' THEN '浙江'
        END,
        province
    ) AS province,
    area_size,
    open_date,
    ROUND(TIMESTAMPDIFF(MONTH, open_date, CURDATE()) / 12.0, 1) AS open_years,
    status
FROM (
    SELECT *,
        ROW_NUMBER() OVER (PARTITION BY store_id ORDER BY load_time DESC) AS rn
    FROM shop_dm.ods_store
    WHERE DATE(load_time) <= CAST(@etl_date AS DATE)
) t
WHERE rn = 1;
