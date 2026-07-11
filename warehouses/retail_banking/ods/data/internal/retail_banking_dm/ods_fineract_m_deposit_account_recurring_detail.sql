-- Deterministic smoke data for Fineract m_deposit_account_recurring_detail
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_deposit_account_recurring_detail;

INSERT INTO retail_banking_dm.ods_fineract_m_deposit_account_recurring_detail (
    `id`,
    `savings_account_id`,
    `mandatory_recommended_deposit_amount`,
    `is_mandatory`,
    `allow_withdrawal`,
    `adjust_advance_towards_future_payments`,
    `is_calendar_inherited`,
    `total_overdue_amount`,
    `no_of_overdue_installments`,
    `load_time`
) VALUES
    (
        1,
        1,
        100.000000,
        FALSE,
        FALSE,
        FALSE,
        FALSE,
        100.000000,
        1,
        '2025-01-15 00:00:00'
    );
