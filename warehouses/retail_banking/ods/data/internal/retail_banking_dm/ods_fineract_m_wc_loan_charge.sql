-- Deterministic smoke data for Fineract m_wc_loan_charge
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_wc_loan_charge;

INSERT INTO retail_banking_dm.ods_fineract_m_wc_loan_charge (
    `id`,
    `loan_id`,
    `charge_id`,
    `is_penalty`,
    `charge_time_type`,
    `charge_calculation_type`,
    `charge_payment_mode`,
    `calculation_on_amount`,
    `amount_paid`,
    `amount`,
    `is_paid`,
    `is_active`,
    `due_date`,
    `created_by`,
    `last_modified_by`,
    `external_id`,
    `submitted_on_date`,
    `created_on_utc`,
    `last_modified_on_utc`,
    `load_time`
) VALUES
    (
        1,
        1,
        1,
        FALSE,
        1,
        1,
        1,
        100.000000,
        100.000000,
        100.000000,
        FALSE,
        FALSE,
        '2025-01-15',
        1,
        1,
        '00000000-0000-4000-8000-000000000001',
        '2025-01-15',
        '2025-01-15 09:00:00',
        '2025-01-15 09:00:00',
        '2025-01-15 00:00:00'
    );
