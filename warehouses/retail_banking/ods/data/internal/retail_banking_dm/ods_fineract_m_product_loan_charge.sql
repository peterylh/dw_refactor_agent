-- Deterministic smoke data for Fineract m_product_loan_charge
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_product_loan_charge;

INSERT INTO retail_banking_dm.ods_fineract_m_product_loan_charge (
    `product_loan_id`,
    `charge_id`,
    `load_time`
) VALUES
    (
        1,
        1,
        '2025-01-15 00:00:00'
    );
