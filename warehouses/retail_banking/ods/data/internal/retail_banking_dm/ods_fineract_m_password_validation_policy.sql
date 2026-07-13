-- Deterministic smoke data for Fineract m_password_validation_policy
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_password_validation_policy;

INSERT INTO retail_banking_dm.ods_fineract_m_password_validation_policy (
    `id`,
    `regex`,
    `description`,
    `active`,
    `key`,
    `load_time`
) VALUES
    (
        1,
        'm_password_validation_policy_regex_1',
        'm_password_validation_policy_description_1',
        FALSE,
        'm_password_validation_policy_key_1',
        '2025-01-15 00:00:00'
    );
