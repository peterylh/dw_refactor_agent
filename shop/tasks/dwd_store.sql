-- ============================================================
-- 加工作业: DWD 门店维度宽表
-- 源表: ods_store
-- 加工逻辑: 门店分级 -> 计算开业年限 -> 补全缺失值
-- ============================================================

-- Step 1: 清空目标表
TRUNCATE TABLE shop_dm.dwd_store;

-- Step 2: 全量加载 + 门店评级 + 开业年限
INSERT INTO shop_dm.dwd_store
SELECT
    store_id,
    store_name,
    store_type,
    CASE
        WHEN area_size >= 3000 THEN 'A级'
        WHEN area_size >= 1000 THEN 'B级'
        ELSE 'C级'
    END AS store_level,
    address,
    city,
    province,
    area_size,
    open_date,
    ROUND(TIMESTAMPDIFF(MONTH, open_date, CURDATE()) / 12.0, 1) AS open_years,
    status,
    NOW() AS etl_time
FROM shop_dm.ods_store;

-- Step 3: 门店类型缺失时按面积推断
UPDATE shop_dm.dwd_store
SET store_type = CASE
    WHEN area_size >= 3000 THEN '旗舰店'
    WHEN area_size >= 1000 THEN '标准店'
    ELSE '社区店'
END
WHERE store_type IS NULL OR store_type = '';

-- Step 4: 省份为空时根据城市映射补齐
UPDATE shop_dm.dwd_store
SET province = CASE
    WHEN city = '北京' THEN '北京'
    WHEN city = '上海' THEN '上海'
    WHEN city IN ('广州','深圳') THEN '广东'
    WHEN city = '成都' THEN '四川'
    WHEN city = '杭州' THEN '浙江'
    ELSE province
END
WHERE province IS NULL;
