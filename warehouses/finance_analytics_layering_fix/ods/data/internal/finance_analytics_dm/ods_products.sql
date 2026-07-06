INSERT INTO finance_analytics_dm.ods_products (product_id, product_name, category, interest_rate, min_balance, monthly_fee, overdraft_limit, product_tier, is_premium, created_at, load_time)
VALUES
(1, 'Checking Account', 'Deposit', 0.01, 0, 0, 100, 'Basic', FALSE, '2025-01-01 09:00:00', '2025-01-15 09:00:00'),
(2, 'Savings Account', 'Deposit', 0.03, 100, 0, 0, 'Standard', FALSE, '2025-01-02 09:00:00', '2025-01-15 09:00:00'),
(3, 'Rewards Credit Card', 'Credit', 0.18, 0, 0, 0, 'Premium', TRUE, '2025-01-03 09:00:00', '2025-01-15 09:00:00'),
(4, 'Personal Loan', 'Loan', 0.08, 0, 0, 0, 'Standard', FALSE, '2025-01-04 09:00:00', '2025-01-15 09:00:00'),
(5, 'Mortgage', 'Loan', 0.05, 0, 0, 0, 'Premium', TRUE, '2025-01-05 09:00:00', '2025-01-15 09:00:00'),
(6, 'Investment Account', 'Investment', 0.0, 1000, 25, 0, 'Premium', TRUE, '2025-01-06 09:00:00', '2025-01-15 09:00:00');
