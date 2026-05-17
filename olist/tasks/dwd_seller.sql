-- ============================================================
-- 加工作业: DWD 卖家明细维表(纯维度)
-- 源表: ods_seller
-- 加工逻辑: 地理区域划分 -> 补全缺失值
-- ============================================================

-- Step 1: 清空目标表
TRUNCATE TABLE olist_dm.dwd_seller;

-- Step 2: 全量加载维度 + 区域划分
INSERT INTO olist_dm.dwd_seller
SELECT
    seller_id,
    seller_city,
    seller_state,
    CASE
        WHEN seller_state IN ('AC','AP','AM','PA','RO','RR','TO') THEN 'Norte'
        WHEN seller_state IN ('AL','BA','CE','MA','PB','PE','PI','RN','SE') THEN 'Nordeste'
        WHEN seller_state IN ('DF','GO','MT','MS') THEN 'Centro-Oeste'
        WHEN seller_state IN ('ES','MG','RJ','SP') THEN 'Sudeste'
        WHEN seller_state IN ('PR','RS','SC') THEN 'Sul'
        ELSE 'Desconhecido'
    END AS seller_region,
    seller_zip_code_prefix,
    NOW() AS etl_time
FROM olist_dm.ods_seller;

-- Step 3: 城市为空填充
UPDATE olist_dm.dwd_seller
SET seller_city = 'desconhecido'
WHERE seller_city IS NULL OR seller_city = '';

-- Step 4: 区域为空填充
UPDATE olist_dm.dwd_seller
SET seller_region = 'Desconhecido'
WHERE seller_region IS NULL;
