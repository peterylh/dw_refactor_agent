-- DWD 客户明细宽表
DROP TABLE IF EXISTS shop_dm.dwd_customer;
CREATE TABLE IF NOT EXISTS shop_dm.dwd_customer (
    customer_id    BIGINT       NOT NULL COMMENT '客户ID',
    customer_name  VARCHAR(64)  NOT NULL COMMENT '客户姓名',
    gender         VARCHAR(4)   NULL COMMENT '性别',
    age            INT          NULL COMMENT '年龄',
    age_group      VARCHAR(16)  NULL COMMENT '年龄段:青年/中年/中老年/老年',
    phone          VARCHAR(20)  NULL COMMENT '手机号',
    email          VARCHAR(128) NULL COMMENT '邮箱',
    address        VARCHAR(256) NULL COMMENT '地址',
    city           VARCHAR(64)  NULL COMMENT '城市',
    province       VARCHAR(64)  NULL COMMENT '省份',
    member_level   VARCHAR(16)  NULL COMMENT '会员等级',
    register_date  DATE         NULL COMMENT '注册日期',
    etl_time       DATETIME     NOT NULL COMMENT 'ETL处理时间'
) ENGINE=OLAP
UNIQUE KEY(customer_id)
DISTRIBUTED BY HASH(customer_id) BUCKETS 10
PROPERTIES (
    "replication_num" = "1"
);
