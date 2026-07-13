-- ODS mirror of Apache Fineract m_savings_interest_incentives (存款与储蓄)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_savings_interest_incentives;
-- table_id: 7de595f4-29d0-4c1e-b70b-0972f59f8bb6
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_savings_interest_incentives (
    -- column_id: 61f06b5b-c212-4409-b3b1-3ce41ecf35e2
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 67a96ca4-0141-4da7-bce8-db200048dd65
    `deposit_account_interest_rate_slab_id` BIGINT NOT NULL COMMENT 'Fineract source column deposit_account_interest_rate_slab_id',
    -- column_id: fa5733e7-0580-4e40-94d2-945f4c246710
    `entiry_type` SMALLINT NOT NULL COMMENT 'Fineract source column entiry_type',
    -- column_id: d2c1ae64-13a9-4882-93fb-c66ed2b22421
    `attribute_name` SMALLINT NOT NULL COMMENT 'Fineract source column attribute_name',
    -- column_id: d01a7853-54b3-4cce-9d39-9cc873fd681f
    `condition_type` SMALLINT NOT NULL COMMENT 'Fineract source column condition_type',
    -- column_id: cad3cc94-7d71-4aba-9343-dbeb22f1a668
    `attribute_value` VARCHAR(50) NOT NULL COMMENT 'Fineract source column attribute_value',
    -- column_id: 47ddf7c7-9a37-46bb-b8d8-8cb23659cc61
    `incentive_type` SMALLINT NOT NULL COMMENT 'Fineract source column incentive_type',
    -- column_id: 50e8cafe-d0c2-4718-9e28-7f91cd4c2fee
    `amount` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column amount',
    -- column_id: 779420ad-c0ca-4b65-828f-3455c0681426
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
