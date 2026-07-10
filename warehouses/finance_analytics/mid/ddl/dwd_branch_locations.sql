DROP TABLE IF EXISTS finance_analytics_dm.dwd_branch_locations;
-- table_id: c8bec1a6-e39f-4c44-bdd6-a804d66b97ca
CREATE TABLE IF NOT EXISTS finance_analytics_dm.dwd_branch_locations (
    -- column_id: b16518e0-e349-45f9-a3f6-4d0ae483a651
    branch_id BIGINT NULL,
    -- column_id: 7cd3b375-521a-46da-8c7d-0502510ba443
    branch_code STRING NULL,
    -- column_id: 6207b0de-9545-4ac7-96da-56dfc084b246
    branch_name STRING NULL,
    -- column_id: fa18a608-ebe2-4e25-9100-95b1fddf1c47
    branch_type STRING NULL,
    -- column_id: 919a3349-5bb3-496a-9b81-61a615c4e988
    region STRING NULL,
    -- column_id: 91865026-3c7d-4124-a15b-4b9c089f80e2
    address STRING NULL,
    -- column_id: 15bbcf75-6933-4c88-801c-f0ddd9d1fdbf
    city STRING NULL,
    -- column_id: 7cb94126-204d-4ac7-a0c3-12a2fe9ec3fc
    state STRING NULL,
    -- column_id: 26022cff-ddc5-473e-a058-380900194995
    zip_code STRING NULL,
    -- column_id: d4d8b369-d0b0-4fb0-aac3-697abdc12720
    country STRING NULL,
    -- column_id: 910fec70-1de2-4552-8a85-00ae1c16ecbe
    latitude DECIMAL(18,4) NULL,
    -- column_id: afb25a74-e5cd-416e-aa02-483315b8bf2e
    longitude DECIMAL(18,4) NULL,
    -- column_id: ed4a72fc-0eb4-4e69-aa53-7c1c8dbaa0c1
    phone STRING NULL,
    -- column_id: 78845d4a-937b-446d-8e86-45706d464a75
    open_date DATETIME NULL,
    -- column_id: 8136cc2c-f307-429f-bc1d-882638f738f0
    is_active BOOLEAN NULL,
    -- column_id: 15c453b6-8686-497b-b766-05707bfafaec
    operating_hours STRING NULL,
    -- column_id: 59f70564-dcff-4281-80d5-3eb2c4ec4516
    square_footage STRING NULL,
    -- column_id: 1ab6e5b3-9bb1-4cf1-8bf0-870b10974e34
    num_employees BIGINT NULL,
    -- column_id: 50f7a097-4b93-4997-a7b3-15ad41793c78
    avg_daily_customers STRING NULL,
    -- column_id: 0938aa10-4b2e-4527-af38-29a4df0dce1b
    has_safe_deposit BOOLEAN NULL,
    -- column_id: 58862f60-9d5d-4173-952e-ab1ab3c4ad1e
    has_notary BOOLEAN NULL,
    -- column_id: 019e2f2c-fd00-4ba8-8a9b-9d40e261d5c1
    has_coin_counter BOOLEAN NULL,
    -- column_id: 837dbee5-ab21-4679-8dcf-cdc8af31adc3
    wheelchair_accessible STRING NULL,
    -- column_id: 763fcb5f-ef3b-4397-bc65-be0b652dcbb0
    manager_name STRING NULL,
    -- column_id: 2a1b8158-8c3c-4650-b7e2-a4b1a0fd5946
    created_at DATETIME NULL
) ENGINE=OLAP
DUPLICATE KEY(branch_id)
DISTRIBUTED BY HASH(branch_id) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
