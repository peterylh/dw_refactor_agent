-- Deterministic smoke data for Fineract m_meeting
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_meeting;

INSERT INTO retail_banking_dm.ods_fineract_m_meeting (
    `id`,
    `calendar_instance_id`,
    `meeting_date`,
    `load_time`
) VALUES
    (
        1,
        1,
        '2025-01-15',
        '2025-01-15 00:00:00'
    );
