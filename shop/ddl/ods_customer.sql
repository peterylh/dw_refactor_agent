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
DISTRIBUTED BY HASH(customer_id) BUCKETS 10
PARTITION BY RANGE(create_time) (
    PARTITION p20250101 VALUES LESS THAN ("2025-01-02"),
    PARTITION p20250102 VALUES LESS THAN ("2025-01-03"),
    PARTITION p20250103 VALUES LESS THAN ("2025-01-04"),
    PARTITION p_future VALUES LESS THAN MAXVALUE
)
PROPERTIES (
    "replication_num" = "1"
);

-- 样例数据
INSERT INTO shop_dm.ods_customer VALUES
(1001, '张伟',   '男', 35, '13800001001', 'zhangwei@email.com',   '朝阳区建国路88号',    '北京', '北京', '金卡',   '2024-01-15', '2025-01-01 08:00:00'),
(1002, '李娜',   '女', 28, '13800001002', 'lina@email.com',       '浦东新区陆家嘴路100号', '上海', '上海', '银卡',   '2024-02-20', '2025-01-01 08:00:00'),
(1003, '王强',   '男', 42, '13800001003', 'wangqiang@email.com',  '天河区体育西路55号',   '广州', '广东', '钻石',  '2024-03-10', '2025-01-01 08:00:00'),
(1004, '赵敏',   '女', 31, '13800001004', 'zhaomin@email.com',    '南山区科技园路12号',   '深圳', '广东', '金卡',   '2024-04-05', '2025-01-02 08:00:00'),
(1005, '刘洋',   '男', 25, '13800001005', 'liuyang@email.com',    '武侯区天府大道200号',  '成都', '四川', '普通',  '2024-05-18', '2025-01-02 08:00:00'),
(1006, '陈静',   '女', 38, '13800001006', 'chenjing@email.com',   '西湖区文三路33号',    '杭州', '浙江', '金卡',   '2024-06-22', '2025-01-02 08:00:00'),
(1007, '孙鹏',   '男', 29, '13800001007', 'sunpeng@email.com',    '渝中区解放碑路8号',    '重庆', '重庆', '银卡',   '2024-07-30', '2025-01-02 08:00:00'),
(1008, '周洁',   '女', 45, '13800001008', 'zhoujie@email.com',    '鼓楼区新模范马路66号', '南京', '江苏', '钻石',  '2024-08-12', '2025-01-03 08:00:00'),
(1009, '吴昊',   '男', 33, '13800001009', 'wuhao@email.com',      '历下区泉城路77号',    '济南', '山东', '普通',  '2024-09-05', '2025-01-03 08:00:00'),
(1010, '郑爽',   '女', 26, '13800001010', 'zhengshuang@email.com','和平区南京路99号',    '天津', '天津', '银卡',   '2024-10-11', '2025-01-03 08:00:00');
