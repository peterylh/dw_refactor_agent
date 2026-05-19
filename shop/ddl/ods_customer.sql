-- ODS 客户信息表
-- table_id: 2aaceda8-a2cf-409e-82fa-57158161e20d
DROP TABLE IF EXISTS shop_dm.ods_customer;
CREATE TABLE IF NOT EXISTS shop_dm.ods_customer (
    customer_id   BIGINT       NOT NULL COMMENT '客户ID',
    customer_name VARCHAR(64)  NOT NULL COMMENT '客户姓名',
    gender        VARCHAR(4)   NULL COMMENT '性别',
    age           INT          NULL COMMENT '年龄',
    phone         VARCHAR(20)  NULL COMMENT '手机号',
    email         VARCHAR(128) NULL COMMENT '邮箱',
    address       VARCHAR(256) NULL COMMENT '地址',
    city          VARCHAR(64)  NULL COMMENT '城市',
    province      VARCHAR(64)  NULL COMMENT '省份',
    member_level  VARCHAR(16)  NULL COMMENT '会员等级:普通/银卡/金卡/钻石',
    register_date DATE         NULL COMMENT '注册日期',
    create_time   DATETIME     NOT NULL COMMENT '创建时间'
) ENGINE=OLAP
DUPLICATE KEY(customer_id)
PARTITION BY RANGE(create_time) (
    PARTITION p20250101 VALUES LESS THAN ("2025-01-02"),
    PARTITION p20250102 VALUES LESS THAN ("2025-01-03"),
    PARTITION p20250103 VALUES LESS THAN ("2025-01-04"),
    PARTITION p_future VALUES LESS THAN MAXVALUE
)
DISTRIBUTED BY HASH(customer_id) BUCKETS 10
PROPERTIES (
    "replication_num" = "1"
);

-- 样例数据
