-- Deterministic smoke data for Fineract m_loan_originator
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_loan_originator;

INSERT INTO retail_banking_dm.ods_fineract_m_loan_originator (
    `id`,
    `external_id`,
    `name`,
    `status`,
    `originator_type_cv_id`,
    `channel_type_cv_id`,
    `created_on_utc`,
    `created_by`,
    `last_modified_on_utc`,
    `last_modified_by`,
    `load_time`
) VALUES
    (
        1,
        '00000000-0000-4000-8000-000000000001',
        'Synthetic m_loan_originator 1',
        'm_loan_originator_st',
        1,
        1,
        '2025-01-15 09:00:00',
        1,
        '2025-01-15 09:00:00',
        1,
        '2025-01-15 00:00:00'
    );
