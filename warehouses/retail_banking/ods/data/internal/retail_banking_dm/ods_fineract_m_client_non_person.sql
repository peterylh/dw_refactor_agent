-- Deterministic smoke data for Fineract m_client_non_person
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_client_non_person;

INSERT INTO retail_banking_dm.ods_fineract_m_client_non_person (
    `id`,
    `client_id`,
    `constitution_cv_id`,
    `incorp_no`,
    `incorp_validity_till`,
    `main_business_line_cv_id`,
    `remarks`,
    `load_time`
) VALUES
    (
        1,
        1,
        1,
        'm_client_non_person_incorp_no_1',
        '2025-01-15',
        1,
        'm_client_non_person_remarks_1',
        '2025-01-15 00:00:00'
    );
