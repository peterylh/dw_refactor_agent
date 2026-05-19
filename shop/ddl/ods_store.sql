-- ODS 门店信息表
-- table_id: 9b80e880-ad2c-444d-92c5-c01b8130a0a1
DROP TABLE IF EXISTS shop_dm.ods_store;
CREATE TABLE IF NOT EXISTS shop_dm.ods_store (
    store_id    BIGINT       NOT NULL COMMENT '门店ID',
    store_name  VARCHAR(128) NOT NULL COMMENT '门店名称',
    store_type  VARCHAR(32)  NULL COMMENT '门店类型:旗舰店/标准店/社区店',
    address     VARCHAR(256) NULL COMMENT '地址',
    city        VARCHAR(64)  NULL COMMENT '城市',
    province    VARCHAR(64)  NULL COMMENT '省份',
    area_size   DECIMAL(8,2) NULL COMMENT '面积(平方米)',
    open_date   DATE         NULL COMMENT '开业日期',
    status      TINYINT      NOT NULL DEFAULT 1 COMMENT '状态:1营业/0歇业',
    create_time DATETIME     NOT NULL COMMENT '创建时间'
) ENGINE=OLAP
DUPLICATE KEY(store_id)
PARTITION BY RANGE(create_time) (
    PARTITION p20250101 VALUES LESS THAN ("2025-01-02"),
    PARTITION p20250102 VALUES LESS THAN ("2025-01-03"),
    PARTITION p20250103 VALUES LESS THAN ("2025-01-04"),
    PARTITION p_future VALUES LESS THAN MAXVALUE
)
DISTRIBUTED BY HASH(store_id) BUCKETS 10
PROPERTIES (
    "replication_num" = "1"
);

INSERT INTO shop_dm.ods_store VALUES
(3001, '北京朝阳旗舰店', '旗舰店', '朝阳区建国路100号',   '北京', '北京', 5000.00, '2022-01-15', 1, '2025-01-01 08:00:00'),
(3002, '上海浦东标准店', '标准店', '浦东新区张杨路200号',  '上海', '上海', 2000.00, '2022-03-20', 1, '2025-01-01 08:00:00'),
(3003, '广州天河社区店', '社区店', '天河区体育东路88号',   '广州', '广东',  800.00, '2022-06-10', 1, '2025-01-02 08:00:00'),
(3004, '深圳南山标准店', '标准店', '南山区科技路66号',     '深圳', '广东', 1800.00, '2022-08-05', 1, '2025-01-02 08:00:00'),
(3005, '成都武侯社区店', '社区店', '武侯区科华北路50号',   '成都', '四川',  750.00, '2022-10-18', 1, '2025-01-03 08:00:00'),
(3006, '杭州西湖标准店', '标准店', '西湖区文二西路30号',   '杭州', '浙江', 1600.00, '2023-02-14', 1, '2025-01-03 08:00:00');
