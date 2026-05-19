-- ADS 门店绩效评估表
-- table_id: b6e00810-e675-41a8-bc53-22b826fa1e23
DROP TABLE IF EXISTS shop_dm.ads_store_performance;
CREATE TABLE IF NOT EXISTS shop_dm.ads_store_performance (
    store_id         BIGINT        NOT NULL COMMENT '门店ID',
    stat_month       VARCHAR(7)    NOT NULL COMMENT '统计月份:YYYY-MM',
    stat_month_date  DATE          NOT NULL COMMENT '统计月份(月初日期)',
    store_name       VARCHAR(128)  NULL COMMENT '门店名称',
    city             VARCHAR(64)   NULL COMMENT '城市',
    store_type       VARCHAR(32)   NULL COMMENT '门店类型',
    total_orders     INT           NULL COMMENT '总订单数',
    total_amount     DECIMAL(14,2) NULL COMMENT '总销售额',
    customer_count   INT           NULL COMMENT '客户数',
    avg_order_amount DECIMAL(10,2) NULL COMMENT '客单价',
    performance_score DECIMAL(5,2) NULL COMMENT '绩效评分',
    etl_time         DATETIME      NOT NULL COMMENT 'ETL处理时间'
) ENGINE=OLAP
UNIQUE KEY(store_id, stat_month, stat_month_date)
PARTITION BY RANGE(stat_month_date) (
    PARTITION p202501 VALUES LESS THAN ("2025-02-01"),
    PARTITION p202502 VALUES LESS THAN ("2025-03-01"),
    PARTITION p202503 VALUES LESS THAN ("2025-04-01"),
    PARTITION p202504 VALUES LESS THAN ("2025-05-01"),
    PARTITION p202505 VALUES LESS THAN ("2025-06-01"),
    PARTITION p_future VALUES LESS THAN MAXVALUE
)
DISTRIBUTED BY HASH(store_id) BUCKETS 10
PROPERTIES (
    "replication_num" = "1"
);

INSERT INTO shop_dm.ads_store_performance VALUES
(3001, '2025-01', '2025-01-01', '北京朝阳旗舰店', '北京', '旗舰店', 120, 50000.00, 100, 416.67, 85.50, '2025-01-31 23:59:59'),
(3002, '2025-01', '2025-01-01', '上海浦东旗舰店', '上海', '旗舰店', 150, 62500.00, 120, 416.67, 90.00, '2025-01-31 23:59:59'),
(3003, '2025-01', '2025-01-01', '广州天河标准店', '广州', '标准店', 80, 32000.00, 65, 400.00, 78.50, '2025-01-31 23:59:59'),
(3004, '2025-01', '2025-01-01', '深圳南山标准店', '深圳', '标准店', 95, 38000.00, 78, 400.00, 80.00, '2025-01-31 23:59:59'),
(3005, '2025-01', '2025-01-01', '成都锦江社区店', '成都', '社区店', 60, 18000.00, 50, 300.00, 72.00, '2025-01-31 23:59:59'),
(3006, '2025-01', '2025-01-01', '杭州西湖社区店', '杭州', '社区店', 55, 16500.00, 45, 300.00, 70.50, '2025-01-31 23:59:59'),
(3001, '2025-02', '2025-02-01', '北京朝阳旗舰店', '北京', '旗舰店', 130, 54000.00, 108, 415.38, 86.00, '2025-02-28 23:59:59'),
(3002, '2025-02', '2025-02-01', '上海浦东旗舰店', '上海', '旗舰店', 160, 67200.00, 128, 420.00, 91.00, '2025-02-28 23:59:59'),
(3003, '2025-02', '2025-02-01', '广州天河标准店', '广州', '标准店', 85, 34000.00, 68, 400.00, 79.00, '2025-02-28 23:59:59'),
(3004, '2025-02', '2025-02-01', '深圳南山标准店', '深圳', '标准店', 100, 40500.00, 82, 405.00, 81.50, '2025-02-28 23:59:59'),
(3005, '2025-02', '2025-02-01', '成都锦江社区店', '成都', '社区店', 62, 18600.00, 52, 300.00, 73.00, '2025-02-28 23:59:59'),
(3006, '2025-02', '2025-02-01', '杭州西湖社区店', '杭州', '社区店', 58, 17400.00, 48, 300.00, 71.00, '2025-02-28 23:59:59'),
(3001, '2025-03', '2025-03-01', '北京朝阳旗舰店', '北京', '旗舰店', 140, 58800.00, 115, 420.00, 88.00, '2025-03-31 23:59:59'),
(3002, '2025-03', '2025-03-01', '上海浦东旗舰店', '上海', '旗舰店', 170, 71400.00, 135, 420.00, 92.00, '2025-03-31 23:59:59'),
(3003, '2025-03', '2025-03-01', '广州天河标准店', '广州', '标准店', 88, 35200.00, 72, 400.00, 80.00, '2025-03-31 23:59:59');
