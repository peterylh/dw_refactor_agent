-- Deterministic smoke data for Fineract m_client_attendance
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_client_attendance;

INSERT INTO retail_banking_dm.ods_fineract_m_client_attendance (
    `id`,
    `client_id`,
    `meeting_id`,
    `attendance_type_enum`,
    `load_time`
) VALUES
    (
        1,
        1,
        1,
        1,
        '2025-01-15 00:00:00'
    );
