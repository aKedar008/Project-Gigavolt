-- mv_queries.sql
-- Run on node C after mv_setup.sql:   mariadb < mv_queries.sql
-- Run it twice (cold, then warm). SHOW PROFILES at the end lists every duration.

USE gigavolt_analytics;
SET SESSION profiling = 1;
SET SESSION profiling_history_size = 100;

-- Q1: aggregates over single columns, whole table
SELECT COUNT(*), SUM(labor_cost), AVG(hours_spent), MAX(claim_amount) FROM mv_service_cs;
SELECT COUNT(*), SUM(labor_cost), AVG(hours_spent), MAX(claim_amount) FROM mv_service_innodb;

-- Q2: labour cost and hours by service type
SELECT service_type, COUNT(*) AS jobs, SUM(labor_cost) AS total_labor, AVG(hours_spent) AS avg_hours
FROM mv_service_cs GROUP BY service_type ORDER BY total_labor DESC;
SELECT service_type, COUNT(*) AS jobs, SUM(labor_cost) AS total_labor, AVG(hours_spent) AS avg_hours
FROM mv_service_innodb GROUP BY service_type ORDER BY total_labor DESC;

-- Q3: top 10 state / model combinations by total labour cost
SELECT state, model, COUNT(*) AS jobs, SUM(labor_cost) AS total_labor
FROM mv_service_cs GROUP BY state, model ORDER BY total_labor DESC LIMIT 10;
SELECT state, model, COUNT(*) AS jobs, SUM(labor_cost) AS total_labor
FROM mv_service_innodb GROUP BY state, model ORDER BY total_labor DESC LIMIT 10;

-- Q4: warranty claim totals by claim status
SELECT claim_status, COUNT(*) AS n, SUM(claim_amount) AS claimed, AVG(approved_amount) AS avg_approved
FROM mv_service_cs GROUP BY claim_status;
SELECT claim_status, COUNT(*) AS n, SUM(claim_amount) AS claimed, AVG(approved_amount) AS avg_approved
FROM mv_service_innodb GROUP BY claim_status;

SHOW PROFILES;
