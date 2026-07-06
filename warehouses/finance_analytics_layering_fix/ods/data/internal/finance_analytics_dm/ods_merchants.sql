INSERT INTO finance_analytics_dm.ods_merchants (merchant_id, merchant_name, category, mcc_code, city, state, country, latitude, longitude, risk_rating, avg_transaction_amount, is_online, established_date, created_at, load_time)
VALUES
(1, 'Fresh Mart', 'Grocery', 5411, 'Boston', 'MA', 'USA', 42.3601, -71.0589, 'High', 89.02, FALSE, '2006-02-06', '2025-01-02 09:00:00', '2025-01-15 09:00:00'),
(2, 'Fuel Point', 'Gas Station', 5541, 'Chicago', 'IL', 'USA', 41.8781, -87.6298, 'High', 183.14, FALSE, '2007-03-07', '2025-01-03 09:00:00', '2025-01-15 09:00:00'),
(3, 'Cloud Store', 'Online Shopping', 5969, 'Dallas', 'TX', 'USA', 32.7767, -96.797, 'Low', 105.23, TRUE, '2008-04-08', '2025-01-04 09:00:00', '2025-01-15 09:00:00'),
(4, 'Health Hub', 'Healthcare', 8099, 'San Francisco', 'CA', 'USA', 37.7749, -122.4194, 'Low', 414.1, FALSE, '2009-05-09', '2025-01-05 09:00:00', '2025-01-15 09:00:00'),
(5, 'Travel Air', 'Travel', 4511, 'Seattle', 'WA', 'USA', 47.6062, -122.3321, 'High', 74.99, TRUE, '2010-06-10', '2025-01-06 09:00:00', '2025-01-15 09:00:00'),
(6, 'Cinema City', 'Entertainment', 7832, 'Miami', 'FL', 'USA', 25.7617, -80.1918, 'Medium', 43.28, FALSE, '2011-07-11', '2025-01-07 09:00:00', '2025-01-15 09:00:00'),
(7, 'Cafe Nova', 'Restaurant', 5812, 'Atlanta', 'GA', 'USA', 33.749, -84.388, 'Low', 150.72, FALSE, '2012-08-12', '2025-01-08 09:00:00', '2025-01-15 09:00:00'),
(8, 'Home Fix', 'Services', 7349, 'New York', 'NY', 'USA', 40.7128, -74.006, 'High', 371.16, FALSE, '2013-09-13', '2025-01-09 09:00:00', '2025-01-15 09:00:00');
