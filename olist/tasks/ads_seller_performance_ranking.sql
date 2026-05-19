-- ============================================================
-- 加工作业: ADS 卖家绩效排名表
-- 源表: dws_seller_monthly, dwd_seller
-- 加工逻辑: 窗口排名 -> 综合评分 -> 修正空值
-- ============================================================

-- Step 1: 清空目标表
TRUNCATE TABLE olist_dm.ads_seller_performance_ranking;

-- Step 2: 按月计算卖家排名和综合绩效分
INSERT INTO olist_dm.ads_seller_performance_ranking
WITH seller_scored AS (
    SELECT
        sm.stat_month,
        sm.seller_id,
        ds.seller_city,
        ds.seller_state,
        sm.order_count,
        sm.total_revenue,
        sm.avg_review_score,
        RANK() OVER (PARTITION BY sm.stat_month ORDER BY sm.total_revenue DESC) AS revenue_rank,
        RANK() OVER (PARTITION BY sm.stat_month ORDER BY sm.avg_review_score DESC) AS score_rank
    FROM olist_dm.dws_seller_monthly sm
    LEFT JOIN olist_dm.dwd_seller ds ON sm.seller_id = ds.seller_id
)
SELECT
    stat_month,
    seller_id,
    seller_city,
    seller_state,
    order_count,
    total_revenue,
    avg_review_score,
    revenue_rank,
    score_rank,
    ROUND(
        (100 - revenue_rank + 1) * 0.6 +
        (CASE WHEN avg_review_score IS NOT NULL THEN avg_review_score * 20 ELSE 60 END) * 0.4, 2
    ) AS performance_score,
    NOW() AS etl_time
FROM seller_scored;

-- Step 3: 城市为空填充
UPDATE olist_dm.ads_seller_performance_ranking
SET seller_city = 'desconhecido'
WHERE seller_city IS NULL;

-- Step 4: 绩效评分空值修正 0
UPDATE olist_dm.ads_seller_performance_ranking
SET performance_score = 0.00
WHERE performance_score IS NULL;
