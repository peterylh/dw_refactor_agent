-- Deterministic smoke data for Fineract m_permission
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_permission;

INSERT INTO retail_banking_dm.ods_fineract_m_permission (
    `id`,
    `grouping`,
    `code`,
    `entity_name`,
    `action_name`,
    `can_maker_checker`,
    `load_time`
) VALUES
    (
        1,
        'm_permission_grouping_1',
        'm_permission_code_1',
        'm_permission_entity_name_1',
        'm_permission_action_name_1',
        FALSE,
        '2025-01-15 00:00:00'
    );
