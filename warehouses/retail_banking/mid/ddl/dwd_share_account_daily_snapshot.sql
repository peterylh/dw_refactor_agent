-- DWD account snapshot generated from m_share_account
DROP TABLE IF EXISTS retail_banking_dm.dwd_share_account_daily_snapshot;
-- table_id: 0d7474e1-3338-4aa4-8bd6-d8f02374d28c
CREATE TABLE IF NOT EXISTS retail_banking_dm.dwd_share_account_daily_snapshot (
    -- column_id: 923250a3-b612-48ae-aaf4-dd3bfaa23720
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 201191c8-4e7d-4d38-b3e4-f9e0e9a60c37
    `snapshot_date` DATE NOT NULL COMMENT 'Warehouse account snapshot date',
    -- column_id: a13cada0-741b-4a1b-9c1d-393192208cbb
    `account_no` VARCHAR(64) NOT NULL COMMENT 'Fineract source column account_no',
    -- column_id: 58cb7599-b3d3-47de-be5d-cbdf6b344c26
    `product_id` BIGINT NOT NULL COMMENT 'Fineract source column product_id',
    -- column_id: 4337e4a8-b86d-40e5-a2ba-eb822abd5353
    `client_id` BIGINT NOT NULL COMMENT 'Fineract source column client_id',
    -- column_id: 07a86608-f6e6-4875-9817-8b0e7a9f9c43
    `external_id` VARCHAR(64) NULL COMMENT 'Fineract source column external_id',
    -- column_id: 160fb5e2-15c8-49cd-b66f-de3f3f9566b8
    `status_enum` SMALLINT NOT NULL COMMENT 'Fineract source column status_enum',
    -- column_id: 1f011bdd-aea0-4c1f-9d1c-9f7d5fbe84ee
    `total_approved_shares` BIGINT NULL COMMENT 'Fineract source column total_approved_shares',
    -- column_id: cb20001b-83a7-4531-9e94-a57a9a24d419
    `total_pending_shares` BIGINT NULL COMMENT 'Fineract source column total_pending_shares',
    -- column_id: 4cf5bb76-bddd-4268-b51b-346b704be2ea
    `submitted_date` DATE NOT NULL COMMENT 'Fineract source column submitted_date',
    -- column_id: cef04dcd-ab8c-4023-a065-daecfcfda7ab
    `submitted_userid` BIGINT NULL COMMENT 'Fineract source column submitted_userid',
    -- column_id: 1692f765-399e-4189-b018-f99964194612
    `approved_date` DATE NULL COMMENT 'Fineract source column approved_date',
    -- column_id: 08a9b182-ed35-4d26-933e-f2a4fe23fdf2
    `approved_userid` BIGINT NULL COMMENT 'Fineract source column approved_userid',
    -- column_id: 3381831b-5e79-40e8-8617-76a3da659024
    `rejected_date` DATE NULL COMMENT 'Fineract source column rejected_date',
    -- column_id: 770b806b-da02-49cf-9c3f-53e75ad078f6
    `rejected_userid` BIGINT NULL COMMENT 'Fineract source column rejected_userid',
    -- column_id: 88a3fdcc-2086-4b16-ba4c-3d588a938aaa
    `activated_date` DATE NULL COMMENT 'Fineract source column activated_date',
    -- column_id: de72d578-5ad9-4a1f-91fe-0db85ec4e38c
    `activated_userid` BIGINT NULL COMMENT 'Fineract source column activated_userid',
    -- column_id: cb385f7f-a602-4b29-a8b6-0ca431ff25bc
    `closed_date` DATE NULL COMMENT 'Fineract source column closed_date',
    -- column_id: 03ef1b80-b595-46a5-a1ad-0f85c9386775
    `closed_userid` BIGINT NULL COMMENT 'Fineract source column closed_userid',
    -- column_id: 991d8b51-683a-4e2b-a698-ac0913fd7004
    `currency_code` VARCHAR(3) NOT NULL COMMENT 'Fineract source column currency_code',
    -- column_id: 36a0e5b6-3f5b-4cd9-862e-a6163ea22b0a
    `currency_digits` SMALLINT NOT NULL COMMENT 'Fineract source column currency_digits',
    -- column_id: f7017c4e-83e7-46b9-858a-3f4a65c483d2
    `currency_multiplesof` SMALLINT NULL COMMENT 'Fineract source column currency_multiplesof',
    -- column_id: 341d2b14-b9d3-42f0-b08b-f7457b544cf6
    `savings_account_id` BIGINT NOT NULL COMMENT 'Fineract source column savings_account_id',
    -- column_id: 3d1c0c53-1e6d-4295-83c2-906e9bf8e4b6
    `minimum_active_period_frequency` DECIMAL(19,6) NULL COMMENT 'Fineract source column minimum_active_period_frequency',
    -- column_id: c27ddcc2-4c19-445d-b1d5-20de5e2aea16
    `minimum_active_period_frequency_enum` SMALLINT NULL COMMENT 'Fineract source column minimum_active_period_frequency_enum',
    -- column_id: 61436b5e-ec38-43ba-9218-ba9f7b00e95b
    `lockin_period_frequency` DECIMAL(19,6) NULL COMMENT 'Fineract source column lockin_period_frequency',
    -- column_id: 87c7f2b8-22bc-4cf6-a969-c3e6eabfcea9
    `lockin_period_frequency_enum` SMALLINT NULL COMMENT 'Fineract source column lockin_period_frequency_enum',
    -- column_id: 19393fc9-ff49-4f36-9491-e5583f2ca3f8
    `allow_dividends_inactive_clients` BOOLEAN NULL COMMENT 'Fineract source column allow_dividends_inactive_clients',
    -- column_id: e2900677-52ff-467b-b825-15e61173be1c
    `created_date` DATETIME NULL COMMENT 'Fineract source column created_date',
    -- column_id: ace1c282-1df5-4491-9e13-cd203fd6b4bd
    `lastmodifiedby_id` BIGINT NULL COMMENT 'Fineract source column lastmodifiedby_id',
    -- column_id: 2de482be-9fa0-4922-aaa0-5fa96c3e56e5
    `lastmodified_date` DATETIME NULL COMMENT 'Fineract source column lastmodified_date',
    -- column_id: d31252db-77a9-4ed2-95f2-6010461a169f
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`, `snapshot_date`)
AUTO PARTITION BY LIST (`snapshot_date`) ()
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
