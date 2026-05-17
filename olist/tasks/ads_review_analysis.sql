-- ============================================================
-- 加工作业: ADS 评价分析表
-- 源表: dwd_order_detail
-- 加工逻辑: 按月+评分汇总 -> 计算占比与配送天数
-- ============================================================

-- Step 1: 清空目标表
TRUNCATE TABLE olist_dm.ads_review_analysis;

-- Step 2: 按月评分汇总
INSERT INTO olist_dm.ads_review_analysis
WITH review_monthly AS (
    SELECT
        order_month AS stat_month,
        review_score,
        COUNT(*) AS review_count,
        ROUND(AVG(delivery_days), 2) AS avg_delivery_days
    FROM olist_dm.dwd_order_detail
    WHERE review_score IS NOT NULL
    GROUP BY order_month, review_score
),
monthly_totals AS (
    SELECT
        stat_month,
        SUM(review_count) AS total_reviews
    FROM review_monthly
    GROUP BY stat_month
)
SELECT
    rm.stat_month,
    rm.review_score,
    rm.review_count,
    ROUND(rm.review_count / NULLIF(mt.total_reviews, 0) * 100, 2) AS score_pct,
    rm.avg_delivery_days,
    NOW() AS etl_time
FROM review_monthly rm
LEFT JOIN monthly_totals mt ON rm.stat_month = mt.stat_month
ORDER BY rm.stat_month, rm.review_score;
