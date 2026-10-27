-- columnstore_setup.sql
-- Run ONLY on the ColumnStore node (node 3):   mariadb < columnstore_setup.sql
--
-- ColumnStore data is NOT replicated by Galera, so everything here is kept local
-- to this node with wsrep_on=OFF and lives in its own database that does not
-- exist on the other nodes.

SET SESSION wsrep_on = OFF;

-- Sanity check: this must list Columnstore with support = YES
SELECT engine, support FROM information_schema.engines WHERE engine = 'Columnstore';

CREATE DATABASE IF NOT EXISTS gigavolt_analytics;
USE gigavolt_analytics;

DROP TABLE IF EXISTS telemetry_cs;
DROP TABLE IF EXISTS telemetry_innodb;
DROP TABLE IF EXISTS eq_map;

-- Same columns in both tables so the comparison is fair.
-- InnoDB gets a normal index; ColumnStore needs (and allows) none.
CREATE TABLE telemetry_innodb (
  equipment_id    VARCHAR(50),
  reading_ts      DATETIME,
  voltage         DECIMAL(6,2),
  current_a       DECIMAL(6,2),
  temperature_c   DECIMAL(5,2),
  state_of_charge DECIMAL(5,2),
  power_kw        DECIMAL(8,2),
  frequency_hz    DECIMAL(5,2),
  humidity_pct    DECIMAL(5,2),
  vibration_mm_s  DECIMAL(6,2),
  cycle_count     INT,
  status_code     VARCHAR(10),
  KEY idx_eq_ts (equipment_id, reading_ts)
) ENGINE=InnoDB;

CREATE TABLE telemetry_cs (
  equipment_id    VARCHAR(50),
  reading_ts      DATETIME,
  voltage         DECIMAL(6,2),
  current_a       DECIMAL(6,2),
  temperature_c   DECIMAL(5,2),
  state_of_charge DECIMAL(5,2),
  power_kw        DECIMAL(8,2),
  frequency_hz    DECIMAL(5,2),
  humidity_pct    DECIMAL(5,2),
  vibration_mm_s  DECIMAL(6,2),
  cycle_count     INT,
  status_code     VARCHAR(10)
) ENGINE=ColumnStore;

-- Number the real equipment IDs from the replicated ERP data so telemetry links to them
CREATE TABLE eq_map (rn INT PRIMARY KEY, equipment_id VARCHAR(50)) ENGINE=InnoDB;

INSERT INTO eq_map
SELECT ROW_NUMBER() OVER (ORDER BY equipment_id) - 1, equipment_id
FROM gigavolt_erp.equipment;

SELECT COUNT(*) INTO @n FROM eq_map;
SELECT IF(@n = 0,
          'ERROR: gigavolt_erp.equipment is empty on this node - fix before continuing',
          CONCAT(@n, ' equipment rows mapped')) AS equipment_check;

-- Generate 2,000,000 readings: one reading per equipment every 3 hours (spans ~100 days)
-- (increase seq_1_to_2000000 for a bigger demo if the instance has the RAM)
INSERT INTO telemetry_innodb
SELECT
  m.equipment_id,
  DATE_ADD('2026-01-01 00:00:00', INTERVAL ((s.seq DIV @n) * 180) MINUTE),
  ROUND(440 + RAND() * 20, 2),
  ROUND(50 + RAND() * 150, 2),
  ROUND(20 + RAND() * 40, 2),
  ROUND(10 + RAND() * 90, 2),
  ROUND(5 + RAND() * 95, 2),
  ROUND(59.5 + RAND(), 2),
  ROUND(20 + RAND() * 60, 2),
  ROUND(RAND() * 10, 2),
  FLOOR(RAND() * 5000),
  CASE WHEN RAND() < 0.01 THEN 'FAULT' WHEN RAND() < 0.06 THEN 'WARN' ELSE 'OK' END
FROM seq_1_to_2000000 s
JOIN eq_map m ON m.rn = s.seq MOD @n;

-- Load the identical rows into ColumnStore
INSERT INTO telemetry_cs
SELECT * FROM telemetry_innodb;

ANALYZE TABLE telemetry_innodb;

-- Count each table in its own query: a single query that mixes InnoDB and
-- ColumnStore tables needs extra cross-engine credentials and fails without them.
SELECT COUNT(*) AS telemetry_innodb_rows FROM telemetry_innodb;
SELECT COUNT(*) AS telemetry_cs_rows FROM telemetry_cs;
SELECT MIN(reading_ts) AS first_reading, MAX(reading_ts) AS last_reading FROM telemetry_cs;
