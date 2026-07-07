INSERT INTO finance_analytics_dm.ods_fraud_alerts (alert_id, transaction_id, customer_id, account_id, alert_date, alert_type, alert_severity, investigation_status, resolution_date, amount_recovered, assigned_to, notes, created_at, load_time)
VALUES
(1, 7, 2, 2, '2025-01-03 11:10:00', 'Velocity Check', 'High', 'Resolved - Fraud', '2025-01-05 11:00:00', 163.33, 'INV001', 'Investigate transaction 7', '2025-01-03 11:00:00', '2025-01-15 09:00:00'),
(2, 18, 4, 5, '2025-01-02 14:10:00', 'Unusual Spending', 'Critical', 'Resolved - Fraud', '2025-01-04 14:00:00', 463.07, 'INV002', 'Investigate transaction 18', '2025-01-02 14:00:00', '2025-01-15 09:00:00'),
(3, 31, 6, 9, '2025-01-03 17:10:00', 'Velocity Check', 'Critical', 'Open', '2025-01-05 17:00:00', 478.46, 'INV003', 'Investigate transaction 31', '2025-01-03 17:00:00', '2025-01-15 09:00:00');
