-- Deterministic smoke data for Fineract acc_gl_closure
TRUNCATE TABLE retail_banking_dm.ods_fineract_acc_gl_closure;

INSERT INTO retail_banking_dm.ods_fineract_acc_gl_closure (
    `id`,
    `office_id`,
    `closing_date`,
    `is_deleted`,
    `createdby_id`,
    `lastmodifiedby_id`,
    `created_date`,
    `lastmodified_date`,
    `comments`,
    `load_time`
) VALUES
    (
        1,
        1,
        '2025-01-15',
        FALSE,
        1,
        1,
        '2025-01-15 09:00:00',
        '2025-01-15 09:00:00',
        'acc_gl_closure_comments_1',
        '2025-01-15 00:00:00'
    );
