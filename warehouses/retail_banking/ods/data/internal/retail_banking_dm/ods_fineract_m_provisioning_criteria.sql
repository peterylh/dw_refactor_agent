-- Deterministic smoke data for Fineract m_provisioning_criteria
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_provisioning_criteria;

INSERT INTO retail_banking_dm.ods_fineract_m_provisioning_criteria (
    `id`,
    `criteria_name`,
    `createdby_id`,
    `created_date`,
    `lastmodifiedby_id`,
    `lastmodified_date`,
    `load_time`
) VALUES
    (
        1,
        'm_provisioning_criteria_criteria_name_1',
        1,
        '2025-01-15 09:00:00',
        1,
        '2025-01-15 09:00:00',
        '2025-01-15 00:00:00'
    );
