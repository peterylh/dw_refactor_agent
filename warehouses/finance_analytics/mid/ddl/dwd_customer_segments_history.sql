DROP TABLE IF EXISTS finance_analytics_dm.dwd_customer_segments_history;
-- table_id: 4a1758f9-e702-45fe-83ec-f946180c1b31
CREATE TABLE IF NOT EXISTS finance_analytics_dm.dwd_customer_segments_history (
    -- column_id: 10d27f66-7b2c-4f20-bbed-cc0b74f3c1c9
    segment_history_id BIGINT NULL,
    -- column_id: dc90de49-f0ac-4dc5-abb6-076ca4748a87
    customer_id BIGINT NULL,
    -- column_id: c8bd3159-9971-4fa3-902f-5ec3ad138ae9
    effective_date DATETIME NULL,
    -- column_id: 308dba1f-df4b-4cdb-92ce-8db300abe801
    end_date DATETIME NULL,
    -- column_id: 570049b7-0bfb-4a50-905a-899b9d07d8fd
    is_current BOOLEAN NULL,
    -- column_id: 01a9a0e6-63e8-4484-8983-52e0f00e9187
    customer_segment STRING NULL,
    -- column_id: 2cef6a2f-eb69-4954-b132-3a426e762a23
    previous_segment STRING NULL,
    -- column_id: d2aa9006-b877-4df2-aab5-1f5f96b292dc
    loyalty_tier STRING NULL,
    -- column_id: bacb772b-998b-415e-be94-c4908d0ae2fb
    previous_tier STRING NULL,
    -- column_id: 15d4b751-1583-4b54-b54d-7279fc604e14
    risk_segment STRING NULL,
    -- column_id: 6aa1d7bf-59d6-4dfa-9114-e19408c0c212
    previous_risk STRING NULL,
    -- column_id: 3eb97ab0-756d-45a2-b291-0adfc1b2d8c8
    change_type STRING NULL,
    -- column_id: 9b5eaacd-c2d1-4fa1-b345-15cf355fddb9
    change_reason STRING NULL,
    -- column_id: 76ecc560-7a7f-4f53-8d31-dfce04e98d61
    triggered_by STRING NULL,
    -- column_id: 02fe2666-cad5-4b69-b9c8-0bccb6fe6441
    total_accounts BIGINT NULL,
    -- column_id: ca8c3744-2c54-4dbc-8cc9-ee0f80cc83c6
    total_balance DECIMAL(18,4) NULL,
    -- column_id: cc055dca-ec9d-46df-934d-d1a2e3831a1a
    avg_monthly_transactions STRING NULL,
    -- column_id: 3f5671a5-1a3a-4439-be1c-2ff7e623c500
    products_held BIGINT NULL,
    -- column_id: 6062dab7-6b60-42ac-9942-be001451022c
    customer_lifetime_value DECIMAL(18,4) NULL,
    -- column_id: eaec6e8e-84d6-4d05-83b8-cdd9dd4e7e76
    tenure_days BIGINT NULL,
    -- column_id: 352a6b5f-6dea-465c-9078-f80f41ef70c2
    credit_score DECIMAL(18,4) NULL,
    -- column_id: 41b7f145-7842-4ce8-ba3e-e206143d25d8
    annual_income DECIMAL(18,4) NULL,
    -- column_id: 6a6813c0-91d7-497f-b4f9-6c6be20cdae4
    last_interaction_days STRING NULL,
    -- column_id: 8c709753-7657-4f52-9a18-ae37270ac4d0
    digital_engagement_score DECIMAL(18,4) NULL,
    -- column_id: 684b4073-e09e-45f3-b0ff-8757e4eeeff1
    branch_visits_last_90d BIGINT NULL,
    -- column_id: b6660b55-a05d-4338-b696-0df71cba51cc
    online_logins_last_90d BIGINT NULL,
    -- column_id: 7e837a5e-2c0b-4945-8b80-fdcaefb5889c
    eligible_for_premium STRING NULL,
    -- column_id: 76347213-b724-4f52-a4ab-d3c0c4ca5740
    churn_risk STRING NULL,
    -- column_id: 4310ea0e-d7aa-43ad-ba58-02f99f2e09af
    cross_sell_opportunity STRING NULL,
    -- column_id: db210420-47d1-4eef-9754-7c048be1bf95
    notes STRING NULL,
    -- column_id: 5c0f36b7-6177-4e5e-bec5-33c49c78237f
    updated_by STRING NULL,
    -- column_id: 17f73136-f47e-4fe5-9a1c-b1ff1b354f09
    created_at DATETIME NULL
) ENGINE=OLAP
DUPLICATE KEY(segment_history_id)
DISTRIBUTED BY HASH(segment_history_id) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
