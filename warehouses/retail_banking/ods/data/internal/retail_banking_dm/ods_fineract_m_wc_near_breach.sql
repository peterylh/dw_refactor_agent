-- Deterministic smoke data for Fineract m_wc_near_breach
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_wc_near_breach;

INSERT INTO retail_banking_dm.ods_fineract_m_wc_near_breach (
    `id`,
    `near_breach_name`,
    `near_breach_frequency`,
    `near_breach_frequency_type`,
    `near_breach_threshold`,
    `load_time`
) VALUES
    (
        1,
        'm_wc_near_breach_near_breach_name_1',
        1,
        'm_wc_near_breach_near_breach_frequency_type_1',
        1,
        '2025-01-15 00:00:00'
    );
