-- columnstore_queries.sql
-- Run on the ColumnStore node after columnstore_setup.sql:   mariadb < columnstore_queries.sql
-- Run it twice: the first run is cold-cache, the second shows warm numbers.
-- SHOW PROFILES at the end lists the duration of every query - screenshot that.

USE gigavolt_analytics;
SET SESSION profiling = 1;
SET SESSION profiling_history_size = 100;

-- Q1: full-table aggregates over a few columns
SELECT COUNT(*), AVG(temperature_c), MAX(power_kw), MIN(voltage) FROM telemetry_cs;
SELECT COUNT(*), AVG(temperature_c), MAX(power_kw), MIN(voltage) FROM telemetry_innodb;

-- Q2: top 10 hottest equipment (group by over the whole table)
SELECT equipment_id, AVG(temperature_c) AS avg_temp, MAX(power_kw) AS peak_kw, COUNT(*) AS readings
FROM telemetry_cs GROUP BY equipment_id ORDER BY avg_temp DESC LIMIT 10;
SELECT equipment_id, AVG(temperature_c) AS avg_temp, MAX(power_kw) AS peak_kw, COUNT(*) AS readings
FROM telemetry_innodb GROUP BY equipment_id ORDER BY avg_temp DESC LIMIT 10;

-- Q3: time-series rollup, daily power and fault counts for February
SELECT DATE(reading_ts) AS day, AVG(power_kw) AS avg_kw,
       SUM(CASE WHEN status_code = 'FAULT' THEN 1 ELSE 0 END) AS faults
FROM telemetry_cs
WHERE reading_ts >= '2026-02-01' AND reading_ts < '2026-03-01'
GROUP BY DATE(reading_ts) ORDER BY DATE(reading_ts);
SELECT DATE(reading_ts) AS day, AVG(power_kw) AS avg_kw,
       SUM(CASE WHEN status_code = 'FAULT' THEN 1 ELSE 0 END) AS faults
FROM telemetry_innodb
WHERE reading_ts >= '2026-02-01' AND reading_ts < '2026-03-01'
GROUP BY DATE(reading_ts) ORDER BY DATE(reading_ts);

-- Q4: health summary by status code
SELECT status_code, COUNT(*) AS readings, AVG(temperature_c) AS avg_temp, AVG(vibration_mm_s) AS avg_vibration
FROM telemetry_cs GROUP BY status_code;
SELECT status_code, COUNT(*) AS readings, AVG(temperature_c) AS avg_temp, AVG(vibration_mm_s) AS avg_vibration
FROM telemetry_innodb GROUP BY status_code;

SHOW PROFILES;
