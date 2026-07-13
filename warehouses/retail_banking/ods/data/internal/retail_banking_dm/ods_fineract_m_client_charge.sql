-- Deterministic smoke data for Fineract m_client_charge
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_client_charge;

INSERT INTO retail_banking_dm.ods_fineract_m_client_charge (
    `id`,
    `client_id`,
    `charge_id`,
    `is_penalty`,
    `charge_time_enum`,
    `charge_due_date`,
    `charge_calculation_enum`,
    `amount`,
    `amount_paid_derived`,
    `amount_waived_derived`,
    `amount_writtenoff_derived`,
    `amount_outstanding_derived`,
    `is_paid_derived`,
    `waived`,
    `is_active`,
    `inactivated_on_date`,
    `load_time`
) VALUES
    (
        1,
        1,
        1,
        FALSE,
        1,
        '2025-01-15',
        1,
        100.000000,
        100.000000,
        100.000000,
        100.000000,
        100.000000,
        FALSE,
        FALSE,
        FALSE,
        '2025-01-15',
        '2025-01-15 00:00:00'
    );
