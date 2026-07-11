-- Deterministic smoke data for Fineract m_collateral_management
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_collateral_management;

INSERT INTO retail_banking_dm.ods_fineract_m_collateral_management (
    `id`,
    `name`,
    `quality`,
    `base_price`,
    `unit_type`,
    `pct_to_base`,
    `currency`,
    `load_time`
) VALUES
    (
        1,
        'Synthetic m_collateral_management 1',
        'm_collateral_management_quality_1',
        1,
        'm_collater',
        1,
        1,
        '2025-01-15 00:00:00'
    );
