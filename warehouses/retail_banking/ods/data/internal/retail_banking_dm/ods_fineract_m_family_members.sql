-- Deterministic smoke data for Fineract m_family_members
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_family_members;

INSERT INTO retail_banking_dm.ods_fineract_m_family_members (
    `id`,
    `client_id`,
    `firstname`,
    `middlename`,
    `lastname`,
    `qualification`,
    `relationship_cv_id`,
    `marital_status_cv_id`,
    `gender_cv_id`,
    `date_of_birth`,
    `age`,
    `profession_cv_id`,
    `mobile_number`,
    `is_dependent`,
    `load_time`
) VALUES
    (
        1,
        1,
        'Synthetic m_family_members 1',
        'm_family_members_middlename_1',
        'Synthetic m_family_members 1',
        'm_family_members_qualification_1',
        1,
        1,
        1,
        '2025-01-15',
        1,
        1,
        '15500000001',
        FALSE,
        '2025-01-15 00:00:00'
    );
