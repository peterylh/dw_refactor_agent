-- ============================================================
-- 加工作业: DWD 订单明细事实表
-- 源表: ods_order, ods_order_item, ods_product, ods_category_translation, ods_payment, ods_review
-- 加工逻辑: 多表关联 -> 品类翻译 -> 配送天数计算 -> 延迟判断
--           评价表用子查询去重确保无重复行
-- ============================================================

-- Step 1: 清空目标表
TRUNCATE TABLE olist_dm.dwd_order_detail;

-- Step 2: 关联多表构建订单明细宽表
INSERT INTO olist_dm.dwd_order_detail
SELECT
    oi.order_id,
    oi.order_item_id,
    o.customer_id,
    oi.seller_id,
    oi.product_id,
    p.product_category_name,
    ct.product_category_name_english,
    o.order_status,
    o.order_purchase_timestamp,
    o.order_delivered_customer_date,
    o.order_estimated_delivery_date,
    DATE_FORMAT(o.order_purchase_timestamp, '%Y-%m') AS order_month,
    oi.price,
    oi.freight_value,
    py.payment_type,
    py.payment_installments,
    r.review_score,
    DATEDIFF(o.order_delivered_customer_date, o.order_purchase_timestamp) AS delivery_days,
    DATEDIFF(o.order_estimated_delivery_date, o.order_purchase_timestamp) AS estimated_delivery_days,
    GREATEST(DATEDIFF(o.order_delivered_customer_date, o.order_estimated_delivery_date), 0) AS delivery_delay_days,
    NOW() AS etl_time
FROM olist_dm.ods_order_item oi
INNER JOIN olist_dm.ods_order o ON oi.order_id = o.order_id
LEFT JOIN olist_dm.ods_product p ON oi.product_id = p.product_id
LEFT JOIN olist_dm.ods_category_translation ct ON p.product_category_name = ct.product_category_name
LEFT JOIN olist_dm.ods_payment py ON oi.order_id = py.order_id AND py.payment_sequential = 1
LEFT JOIN (
    SELECT order_id, review_score,
           ROW_NUMBER() OVER (PARTITION BY order_id ORDER BY review_creation_date DESC) AS rn
    FROM olist_dm.ods_review
) r ON oi.order_id = r.order_id AND r.rn = 1;

-- Step 3: 剔除非 delivered 状态订单
DELETE FROM olist_dm.dwd_order_detail
WHERE order_status != 'delivered';

-- Step 4: 支付方式为空使用 boleto 兜底
UPDATE olist_dm.dwd_order_detail
SET payment_type = 'boleto', payment_installments = 1
WHERE payment_type IS NULL OR payment_type = '';

-- Step 5: 评价分为空默认 3 分
UPDATE olist_dm.dwd_order_detail
SET review_score = 3
WHERE review_score IS NULL;

-- Step 6: 品类名为空标记
UPDATE olist_dm.dwd_order_detail
SET product_category_name = 'unknown', product_category_name_english = 'unknown'
WHERE product_category_name IS NULL;

-- Step 7: 配送天数为空时设置 0
UPDATE olist_dm.dwd_order_detail
SET delivery_days = 0, delivery_delay_days = 0
WHERE delivery_days IS NULL;
