SET @etl_date = COALESCE(@etl_date, CURDATE());

-- Human-reviewed semantic target: retail_banking_dm.dwd_share_charge_snapshot
TRUNCATE TABLE retail_banking_dm.dwd_share_charge_snapshot;

INSERT INTO retail_banking_dm.dwd_share_charge_snapshot (
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
    `etl_time`
)
SELECT
    src.`id`,
    src.`account_id`,
    src.`charge_id`,
    src.`charge_time_enum`,
    src.`charge_calculation_enum`,
    src.`charge_payment_mode_enum`,
    src.`calculation_percentage`,
    src.`calculation_on_amount`,
    src.`charge_amount_or_percentage`,
    src.`amount`,
    src.`amount_paid_derived`,
    src.`amount_waived_derived`,
    src.`amount_writtenoff_derived`,
    src.`amount_outstanding_derived`,
    src.`is_paid_derived`,
    src.`waived`,
    src.`min_cap`,
    src.`max_cap`,
    src.`is_active`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.ods_fineract_m_share_account_charge AS src;
