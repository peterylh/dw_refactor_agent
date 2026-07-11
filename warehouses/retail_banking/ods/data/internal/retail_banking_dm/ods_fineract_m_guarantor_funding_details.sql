-- Deterministic smoke data for Fineract m_guarantor_funding_details
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_guarantor_funding_details;

INSERT INTO retail_banking_dm.ods_fineract_m_guarantor_funding_details (
    `id`,
    `guarantor_id`,
    `account_associations_id`,
    `amount`,
    `amount_released_derived`,
    `amount_remaining_derived`,
    `amount_transfered_derived`,
    `status_enum`,
    `load_time`
) VALUES
    (
        1,
        1,
        1,
        100.000000,
        100.000000,
        100.000000,
        100.000000,
        1,
        '2025-01-15 00:00:00'
    );
