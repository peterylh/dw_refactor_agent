-- Deterministic smoke data for Fineract m_share_account_charge
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_share_account_charge;

INSERT INTO retail_banking_dm.ods_fineract_m_share_account_charge (
    `id`,
    `account_id`,
    `charge_id`,
    `charge_time_enum`,
    `charge_calculation_enum`,
    `charge_payment_mode_enum`,
    `calculation_percentage`,
    `calculation_on_amount`,
    `charge_amount_or_percentage`,
    `amount`,
    `amount_paid_derived`,
    `amount_waived_derived`,
    `amount_writtenoff_derived`,
    `amount_outstanding_derived`,
    `is_paid_derived`,
    `waived`,
    `min_cap`,
    `max_cap`,
    `is_active`,
    `load_time`
) VALUES
    (
        1,
        1,
        1,
        1,
        1,
        1,
        1,
        100.000000,
        100.000000,
        100.000000,
        100.000000,
        100.000000,
        100.000000,
        100.000000,
        FALSE,
        FALSE,
        1,
        1,
        FALSE,
        '2025-01-15 00:00:00'
    );
