-- Auto-generated from dbt model
TRUNCATE TABLE finance_analytics_dm.dim_date;

INSERT INTO finance_analytics_dm.dim_date
WITH date_spine AS (
    SELECT DATE_ADD(CAST('2010-01-01' AS DATE), INTERVAL (o.n + t.n * 10 + h.n * 100 + th.n * 1000) DAY) AS date_day
    FROM (SELECT 0 AS n UNION ALL SELECT 1 AS n UNION ALL SELECT 2 AS n UNION ALL SELECT 3 AS n UNION ALL SELECT 4 AS n UNION ALL SELECT 5 AS n UNION ALL SELECT 6 AS n UNION ALL SELECT 7 AS n UNION ALL SELECT 8 AS n UNION ALL SELECT 9 AS n) o
    CROSS JOIN (SELECT 0 AS n UNION ALL SELECT 1 AS n UNION ALL SELECT 2 AS n UNION ALL SELECT 3 AS n UNION ALL SELECT 4 AS n UNION ALL SELECT 5 AS n UNION ALL SELECT 6 AS n UNION ALL SELECT 7 AS n UNION ALL SELECT 8 AS n UNION ALL SELECT 9 AS n) t
    CROSS JOIN (SELECT 0 AS n UNION ALL SELECT 1 AS n UNION ALL SELECT 2 AS n UNION ALL SELECT 3 AS n UNION ALL SELECT 4 AS n UNION ALL SELECT 5 AS n UNION ALL SELECT 6 AS n UNION ALL SELECT 7 AS n UNION ALL SELECT 8 AS n UNION ALL SELECT 9 AS n) h
    CROSS JOIN (SELECT 0 AS n UNION ALL SELECT 1 AS n UNION ALL SELECT 2 AS n UNION ALL SELECT 3 AS n UNION ALL SELECT 4 AS n UNION ALL SELECT 5 AS n UNION ALL SELECT 6 AS n UNION ALL SELECT 7 AS n UNION ALL SELECT 8 AS n UNION ALL SELECT 9 AS n) th
    WHERE DATE_ADD(CAST('2010-01-01' AS DATE), INTERVAL (o.n + t.n * 10 + h.n * 100 + th.n * 1000) DAY) <= CAST('2030-12-31' AS DATE)
)
SELECT
    MD5(CONCAT_WS('||', COALESCE(CAST(date_day AS STRING), '_dbt_null_'))) AS date_key,
    date_day AS date_actual,
    YEAR(date_day) AS year,
    QUARTER(date_day) AS quarter,
    MONTH(date_day) AS month,
    WEEKOFYEAR(date_day) AS week_of_year,
    DAYOFYEAR(date_day) AS day_of_year,
    DAYOFWEEK(date_day) - 1 AS day_of_week,
    DAYNAME(date_day) AS day_name,
    MONTHNAME(date_day) AS month_name,
    DATE_FORMAT(date_day, '%Y-%m') AS year_month,
    CONCAT(YEAR(date_day), '-Q', QUARTER(date_day)) AS year_quarter,
    DAYOFWEEK(date_day) IN (1, 7) AS is_weekend,
    DAYOFWEEK(date_day) = 1 AS is_sunday,
    DAYOFWEEK(date_day) = 7 AS is_saturday,
    STR_TO_DATE(DATE_FORMAT(date_day, '%Y-%m-01'), '%Y-%m-%d') AS first_day_of_month,
    LAST_DAY(date_day) AS last_day_of_month,
    MAKEDATE(YEAR(date_day), 1) + INTERVAL ((QUARTER(date_day) - 1) * 3) MONTH AS first_day_of_quarter,
    DATE_SUB(MAKEDATE(YEAR(date_day), 1) + INTERVAL (QUARTER(date_day) * 3) MONTH, INTERVAL 1 DAY) AS last_day_of_quarter,
    MAKEDATE(YEAR(date_day), 1) AS first_day_of_year,
    DATE_SUB(MAKEDATE(YEAR(date_day) + 1, 1), INTERVAL 1 DAY) AS last_day_of_year,
    DAYOFMONTH(date_day) = 1 AS is_first_day_of_month,
    date_day = LAST_DAY(date_day) AS is_last_day_of_month
FROM date_spine;
