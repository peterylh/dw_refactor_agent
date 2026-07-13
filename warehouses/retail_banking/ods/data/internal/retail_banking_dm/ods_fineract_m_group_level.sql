-- Deterministic smoke data for Fineract m_group_level
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_group_level;

INSERT INTO retail_banking_dm.ods_fineract_m_group_level (
    `id`,
    `parent_id`,
    `super_parent`,
    `level_name`,
    `recursable`,
    `can_have_clients`,
    `load_time`
) VALUES
    (
        1,
        1,
        FALSE,
        'm_group_level_level_name_1',
        FALSE,
        FALSE,
        '2025-01-15 00:00:00'
    );
