-- Deterministic smoke data for Fineract m_deposit_product_recurring_detail
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_deposit_product_recurring_detail;

INSERT INTO retail_banking_dm.ods_fineract_m_deposit_product_recurring_detail (
    `id`,
    `savings_product_id`,
    `is_mandatory`,
    `allow_withdrawal`,
    `adjust_advance_towards_future_payments`,
    `load_time`
) VALUES
    (
        1,
        1,
        FALSE,
        FALSE,
        FALSE,
        '2025-01-15 00:00:00'
    );
