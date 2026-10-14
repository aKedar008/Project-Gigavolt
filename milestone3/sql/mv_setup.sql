-- mv_setup.sql
-- Run ONLY on the ColumnStore node (node C):   mariadb < mv_setup.sql
--
-- MariaDB has no native MATERIALIZED VIEW, so the standard equivalent is used:
--   1. an ordinary view over the existing ERP tables (denormalised service data)
--   2. its result is materialised (copied) into an InnoDB table and a
--      ColumnStore table, duplicated up to ~1,000,000 rows.

-- ---------------------------------------------------------------------------
-- 1. The view (ordinary DDL, replicated by Galera to all three nodes)
-- ---------------------------------------------------------------------------
USE gigavolt_erp;

CREATE OR REPLACE VIEW vw_service_analytics AS
SELECT
  d.dispatch_id,
  d.dispatch_date,
  d.technician,
  d.service_type,
  d.status          AS dispatch_status,
  d.hours_spent,
  d.labor_cost,
  e.equipment_id,
  e.model,
  e.capacity_kw,
  e.status          AS equipment_status,
  c.customer_id,
  c.company_name,
  l.state,
  l.country,
  wc.claim_id,
  wc.claim_amount,
  wc.approved_amount,
  wc.status         AS claim_status
FROM dispatches d
LEFT JOIN equipment       e  ON e.equipment_id = d.equipment_id
LEFT JOIN customers       c  ON c.customer_id  = d.customer_id
LEFT JOIN locations       l  ON l.zip          = c.zip
LEFT JOIN warranty_claims wc ON wc.dispatch_id = d.dispatch_id;

SELECT COUNT(*) AS rows_in_view FROM vw_service_analytics;

-- ---------------------------------------------------------------------------
-- 2. Keep everything below local to this node (ColumnStore is not replicated)
-- ---------------------------------------------------------------------------
SET SESSION wsrep_on = OFF;

CREATE DATABASE IF NOT EXISTS gigavolt_analytics;
USE gigavolt_analytics;

DROP TABLE IF EXISTS mv_service_cs;
DROP TABLE IF EXISTS mv_service_innodb;
DROP TEMPORARY TABLE IF EXISTS tmp_mv;

CREATE TABLE mv_service_innodb (
  dispatch_id      VARCHAR(50),
  dispatch_date    DATE,
  technician       VARCHAR(100),
  service_type     VARCHAR(100),
  dispatch_status  VARCHAR(50),
  hours_spent      DECIMAL(8,2),
  labor_cost       DECIMAL(10,2),
  equipment_id     VARCHAR(50),
  model            VARCHAR(50),
  capacity_kw      INT,
  equipment_status VARCHAR(50),
  customer_id      VARCHAR(50),
  company_name     VARCHAR(100),
  state            VARCHAR(50),
  country          VARCHAR(50),
  claim_id         VARCHAR(50),
  claim_amount     DECIMAL(10,2),
  approved_amount  DECIMAL(10,2),
  claim_status     VARCHAR(50),
  copy_no          INT
) ENGINE=InnoDB;

CREATE TABLE mv_service_cs (
  dispatch_id      VARCHAR(50),
  dispatch_date    DATE,
  technician       VARCHAR(100),
  service_type     VARCHAR(100),
  dispatch_status  VARCHAR(50),
  hours_spent      DECIMAL(8,2),
  labor_cost       DECIMAL(10,2),
  equipment_id     VARCHAR(50),
  model            VARCHAR(50),
  capacity_kw      INT,
  equipment_status VARCHAR(50),
  customer_id      VARCHAR(50),
  company_name     VARCHAR(100),
  state            VARCHAR(50),
  country          VARCHAR(50),
  claim_id         VARCHAR(50),
  claim_amount     DECIMAL(10,2),
  approved_amount  DECIMAL(10,2),
  claim_status     VARCHAR(50),
  copy_no          INT
) ENGINE=ColumnStore;

-- Run the view once into a temporary table, then duplicate it
CREATE TEMPORARY TABLE tmp_mv AS
SELECT * FROM gigavolt_erp.vw_service_analytics;

SELECT COUNT(*) INTO @n FROM tmp_mv;
SET @target = 1000000;
SET @mult = CEIL(@target / @n);

SELECT IF(@n = 0,
          'ERROR: the view returned no rows - check dispatches/equipment on this node',
          CONCAT(@n, ' view rows x ', @mult, ' copies = ', @n * @mult, ' rows')) AS plan;

-- Materialise into InnoDB (duplicating the view result @mult times)
INSERT INTO mv_service_innodb
SELECT t.*, s.seq
FROM tmp_mv t
JOIN seq_1_to_20000 s ON s.seq <= @mult;

-- Same rows into ColumnStore, in 4 chunks (one big insert ran the small node out of memory)
SET @chunk = CEIL(@mult / 4);

INSERT INTO mv_service_cs
SELECT * FROM mv_service_innodb WHERE copy_no <= @chunk;

INSERT INTO mv_service_cs
SELECT * FROM mv_service_innodb WHERE copy_no > @chunk AND copy_no <= 2 * @chunk;

INSERT INTO mv_service_cs
SELECT * FROM mv_service_innodb WHERE copy_no > 2 * @chunk AND copy_no <= 3 * @chunk;

INSERT INTO mv_service_cs
SELECT * FROM mv_service_innodb WHERE copy_no > 3 * @chunk;

ANALYZE TABLE mv_service_innodb;

-- Count each table separately (a query mixing both engines fails)
SELECT COUNT(*) AS mv_service_innodb_rows FROM mv_service_innodb;
SELECT COUNT(*) AS mv_service_cs_rows FROM mv_service_cs;
