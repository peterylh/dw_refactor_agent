-- Deterministic smoke data for Fineract m_tax_component
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_tax_component;

INSERT INTO retail_banking_dm.ods_fineract_m_tax_component (
    `id`,
    `name`,
    `percentage`,
    `debit_account_type_enum`,
    `debit_account_id`,
    `credit_account_type_enum`,
    `credit_account_id`,
    `start_date`,
    `createdby_id`,
    `created_date`,
    `lastmodifiedby_id`,
    `lastmodified_date`,
    `load_time`
) VALUES
    (
        1,
        'Synthetic m_tax_component 1',
        1,
        1,
        1,
        1,
        1,
        '2025-01-15',
        1,
        '2025-01-15 09:00:00',
        1,
        '2025-01-15 09:00:00',
        '2025-01-15 00:00:00'
    );
