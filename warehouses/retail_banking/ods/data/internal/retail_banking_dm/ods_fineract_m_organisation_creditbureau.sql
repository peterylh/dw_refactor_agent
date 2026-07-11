-- Deterministic smoke data for Fineract m_organisation_creditbureau
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_organisation_creditbureau;

INSERT INTO retail_banking_dm.ods_fineract_m_organisation_creditbureau (
    `id`,
    `alias`,
    `creditbureau_id`,
    `is_active`,
    `load_time`
) VALUES
    (
        1,
        'm_organisation_creditbureau_alias_1',
        1,
        FALSE,
        '2025-01-15 00:00:00'
    );
