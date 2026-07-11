-- Deterministic smoke data for Fineract m_provisioning_criteria_definition
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_provisioning_criteria_definition;

INSERT INTO retail_banking_dm.ods_fineract_m_provisioning_criteria_definition (
    `id`,
    `criteria_id`,
    `category_id`,
    `min_age`,
    `max_age`,
    `provision_percentage`,
    `liability_account`,
    `expense_account`,
    `load_time`
) VALUES
    (
        1,
        1,
        1,
        1,
        1,
        1,
        1,
        1,
        '2025-01-15 00:00:00'
    );
