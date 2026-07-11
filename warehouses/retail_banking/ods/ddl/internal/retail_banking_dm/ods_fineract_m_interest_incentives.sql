-- ODS mirror of Apache Fineract m_interest_incentives (其它银行运营)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_interest_incentives;
-- table_id: 1b75e460-4151-4c37-8d26-7d17bc5e5431
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_interest_incentives (
    -- column_id: 5a959c94-88f8-4694-a68b-11fd5423c1a2
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 981efe6e-dc80-4a4d-9490-ff800fc9c19e
    `interest_rate_slab_id` BIGINT NOT NULL COMMENT 'Fineract source column interest_rate_slab_id',
    -- column_id: 0881bb03-188f-4c9f-96d6-7fc377ca51b3
    `entiry_type` SMALLINT NOT NULL COMMENT 'Fineract source column entiry_type',
    -- column_id: 1becd834-2923-42cc-9724-f81765089a25
    `attribute_name` SMALLINT NOT NULL COMMENT 'Fineract source column attribute_name',
    -- column_id: 93bc87a5-7220-4bd8-be88-b5311e010b80
    `condition_type` SMALLINT NOT NULL COMMENT 'Fineract source column condition_type',
    -- column_id: 4a035335-c038-44b5-af1a-7ccf0cf8ef43
    `attribute_value` VARCHAR(50) NOT NULL COMMENT 'Fineract source column attribute_value',
    -- column_id: 018657cb-9045-4f33-884d-606ec76baec6
    `incentive_type` SMALLINT NOT NULL COMMENT 'Fineract source column incentive_type',
    -- column_id: f9419d72-1d7d-42ad-b77b-62512425a731
    `amount` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column amount',
    -- column_id: 50104f9c-ac3d-464a-bbbf-063e49eb6e10
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
