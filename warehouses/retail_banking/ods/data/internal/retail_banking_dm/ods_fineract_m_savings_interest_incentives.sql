-- Deterministic smoke data for Fineract m_savings_interest_incentives
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_savings_interest_incentives;

INSERT INTO retail_banking_dm.ods_fineract_m_savings_interest_incentives (
    `id`,
    `deposit_account_interest_rate_slab_id`,
    `entiry_type`,
    `attribute_name`,
    `condition_type`,
    `attribute_value`,
    `incentive_type`,
    `amount`,
    `load_time`
) VALUES
    (
        1,
        1,
        1,
        1,
        1,
        'm_savings_interest_incentives_attribute_value_1',
        1,
        100.000000,
        '2025-01-15 00:00:00'
    );
