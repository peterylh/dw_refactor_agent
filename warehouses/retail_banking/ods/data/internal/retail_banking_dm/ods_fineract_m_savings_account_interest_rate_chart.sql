-- Deterministic smoke data for Fineract m_savings_account_interest_rate_chart
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_savings_account_interest_rate_chart;

INSERT INTO retail_banking_dm.ods_fineract_m_savings_account_interest_rate_chart (
    `id`,
    `savings_account_id`,
    `name`,
    `description`,
    `from_date`,
    `end_date`,
    `is_primary_grouping_by_amount`,
    `load_time`
) VALUES
    (
        1,
        1,
        'Synthetic m_savings_account_interest_rate_chart 1',
        'm_savings_account_interest_rate_chart_description_1',
        '2025-01-15',
        '2025-01-15',
        FALSE,
        '2025-01-15 00:00:00'
    );
