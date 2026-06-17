INSERT INTO finance_analytics_dm.ods_customer_interactions (interaction_id, customer_id, interaction_date, interaction_type, reason, duration_minutes, sentiment_score, satisfaction_rating, resolved, escalated, agent_id, notes, created_at, load_time)
VALUES
(1, 1, '2025-01-02 14:00:00', 'Phone Call', 'Transaction Dispute', 41, 0.22, 2, TRUE, FALSE, 'AG002', 'Interaction for customer 1', '2025-01-02 14:00:00', '2025-01-15 09:00:00'),
(2, 2, '2025-01-03 14:00:00', 'Chat', 'Account Inquiry', 16, 0.06, 5, TRUE, FALSE, 'AG003', 'Interaction for customer 2', '2025-01-03 14:00:00', '2025-01-15 09:00:00'),
(3, 3, '2025-01-04 14:00:00', 'Chat', 'Transaction Dispute', 42, 0.01, 5, TRUE, FALSE, 'AG004', 'Interaction for customer 3', '2025-01-04 14:00:00', '2025-01-15 09:00:00'),
(4, 4, '2025-01-05 14:00:00', 'Phone Call', 'Technical Support', 27, -0.03, 4, FALSE, FALSE, 'AG005', 'Interaction for customer 4', '2025-01-05 14:00:00', '2025-01-15 09:00:00'),
(5, 5, '2025-01-06 14:00:00', 'Phone Call', 'Transaction Dispute', 26, -0.02, 5, TRUE, FALSE, 'AG001', 'Interaction for customer 5', '2025-01-06 14:00:00', '2025-01-15 09:00:00'),
(6, 6, '2025-01-07 14:00:00', 'Chat', 'Technical Support', 40, -0.55, 2, TRUE, TRUE, 'AG002', 'Interaction for customer 6', '2025-01-07 14:00:00', '2025-01-15 09:00:00'),
(7, 7, '2025-01-08 14:00:00', 'Chat', 'Complaint', 25, -0.44, 5, TRUE, FALSE, 'AG003', 'Interaction for customer 7', '2025-01-08 14:00:00', '2025-01-15 09:00:00'),
(8, 8, '2025-01-09 14:00:00', 'Phone Call', 'Technical Support', 31, -0.52, 4, FALSE, FALSE, 'AG004', 'Interaction for customer 8', '2025-01-09 14:00:00', '2025-01-15 09:00:00'),
(9, 9, '2025-01-10 14:00:00', 'Branch Visit', 'Technical Support', 8, -0.32, 3, TRUE, FALSE, 'AG005', 'Interaction for customer 9', '2025-01-10 14:00:00', '2025-01-15 09:00:00'),
(10, 10, '2025-01-01 14:00:00', 'Chat', 'Technical Support', 36, -0.43, 3, TRUE, FALSE, 'AG001', 'Interaction for customer 10', '2025-01-01 14:00:00', '2025-01-15 09:00:00'),
(11, 11, '2025-01-02 14:00:00', 'Email', 'Complaint', 40, -0.58, 5, TRUE, FALSE, 'AG002', 'Interaction for customer 11', '2025-01-02 14:00:00', '2025-01-15 09:00:00'),
(12, 12, '2025-01-03 14:00:00', 'Phone Call', 'Transaction Dispute', 12, 0.05, 2, FALSE, TRUE, 'AG003', 'Interaction for customer 12', '2025-01-03 14:00:00', '2025-01-15 09:00:00');
