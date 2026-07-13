DROP TABLE IF EXISTS finance_analytics_dm.ods_customer_segments_history;
-- table_id: 2a2d34cf-cc13-40e6-87dc-b0f45c672be4
CREATE TABLE IF NOT EXISTS finance_analytics_dm.ods_customer_segments_history (
    -- column_id: 7faf5a31-e704-4506-a216-1e293683bffd
    segment_history_id BIGINT NULL,
    -- column_id: 563b7fff-ccba-4e08-b78a-425647351670
    customer_id BIGINT NULL,
    -- column_id: 9e3432b9-3f05-4208-8dd2-42e4cf8b94be
    effective_date DATETIME NULL,
    -- column_id: 87ddd319-843f-408f-8b32-2ee91da53361
    end_date DATETIME NULL,
    -- column_id: badccb68-4ec8-4155-a195-0a16245904b3
    is_current BOOLEAN NULL,
    -- column_id: a8811d0a-45c3-48cc-92b2-146265692d9c
    customer_segment STRING NULL,
    -- column_id: 5c01db1f-94ba-4963-9e54-314d8f9368ee
    previous_segment STRING NULL,
    -- column_id: 27cc50ff-817f-4e85-9229-38b3116e9bd2
    loyalty_tier STRING NULL,
    -- column_id: 8e14ff83-2eab-4771-b9ed-dd40ec055011
    previous_tier STRING NULL,
    -- column_id: 31ded174-bfa2-4fb3-a842-ad65e7418fdc
    risk_segment STRING NULL,
    -- column_id: 24b80ac1-45c9-43e0-9316-ab24ca8ecb66
    previous_risk STRING NULL,
    -- column_id: 206cadf1-ad5b-40f8-91dd-58ae2d3f514f
    change_type STRING NULL,
    -- column_id: 7e7c4e54-1d71-4b30-9cc1-02233b97ad82
    change_reason STRING NULL,
    -- column_id: ecb95180-b081-42b5-96e3-72d1ab9ee651
    triggered_by STRING NULL,
    -- column_id: 09540929-35ff-4697-bd56-f442892a569d
    total_accounts BIGINT NULL,
    -- column_id: d7b5fcdf-e85d-4aa4-bca9-557797cb2eb6
    total_balance DECIMAL(18,4) NULL,
    -- column_id: 6284d7b6-f1aa-465d-a26b-551d87b246e1
    avg_monthly_transactions STRING NULL,
    -- column_id: 0742ae33-3818-4b45-9fb7-540a9326e840
    products_held BIGINT NULL,
    -- column_id: 1311bbf7-177e-4b8c-b14a-db96816f8fdc
    customer_lifetime_value DECIMAL(18,4) NULL,
    -- column_id: 2c0315ce-4068-42c1-98b6-c0bc87fdc258
    tenure_days BIGINT NULL,
    -- column_id: d5d973ed-b392-4508-ae69-8cc175d7eb12
    credit_score DECIMAL(18,4) NULL,
    -- column_id: d9fbe36c-69f2-4d27-80fa-199f8708a236
    annual_income DECIMAL(18,4) NULL,
    -- column_id: b04291d0-db5d-46b4-bff2-ab39d549db2a
    last_interaction_days STRING NULL,
    -- column_id: 2b565c34-7f78-4f84-aa2d-2c4640d31e5f
    digital_engagement_score DECIMAL(18,4) NULL,
    -- column_id: 6d455d3c-9f81-4193-b343-8bf7e53fa058
    branch_visits_last_90d BIGINT NULL,
    -- column_id: c8fb49cf-5778-4b71-bb90-a70b4ae4babb
    online_logins_last_90d BIGINT NULL,
    -- column_id: 5d89e33e-9c8e-40a2-ba90-d05ab1c0a3b1
    eligible_for_premium STRING NULL,
    -- column_id: 35f902a0-fedb-4c3e-bdc7-8a311fc011f5
    churn_risk STRING NULL,
    -- column_id: b5d60c31-321e-4c09-9b7a-af3e1517bdf6
    cross_sell_opportunity STRING NULL,
    -- column_id: 5da79b9c-fafc-4f9b-b5f9-fcedbb44bd19
    notes STRING NULL,
    -- column_id: 8b9e076f-3d36-42db-9849-5ce9b7f606a0
    updated_by STRING NULL,
    -- column_id: 756fe4d0-308a-449a-963a-c45ddc0c5aab
    load_time DATETIME NULL
) ENGINE=OLAP
DUPLICATE KEY(segment_history_id)
DISTRIBUTED BY HASH(segment_history_id) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
