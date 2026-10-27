USE gigavolt_erp;

-- ============================================================
-- MILESTONE 2: SQL Programming, RAG Payloads, Audit, Security
-- ============================================================


-- ============================================================
-- 1. GENERATED COLUMNS FOR RAG-READY TEXT
-- ============================================================

-- Add generated column to equipment table
ALTER TABLE equipment
ADD COLUMN equipment_context TEXT
GENERATED ALWAYS AS (
    CONCAT(
        'Equipment ID: ', IFNULL(equipment_id, ''), '. ',
        'Model: ', IFNULL(model, ''), '. ',
        'Serial Number: ', IFNULL(serial_number, ''), '. ',
        'Capacity KW: ', IFNULL(capacity_kw, ''), '. ',
        'Voltage: ', IFNULL(voltage, ''), '. ',
        'Install Date: ', IFNULL(install_date, ''), '. ',
        'Warranty Expiration: ', IFNULL(warranty_expiration, ''), '. ',
        'Status: ', IFNULL(status, ''), '. ',
        'Location Notes: ', IFNULL(location_notes, ''), '.'
    )
) VIRTUAL;


-- Add generated column to dispatches table
ALTER TABLE dispatches
ADD COLUMN service_context TEXT
GENERATED ALWAYS AS (
    CONCAT(
        'Dispatch ID: ', IFNULL(dispatch_id, ''), '. ',
        'Equipment ID: ', IFNULL(equipment_id, ''), '. ',
        'Customer ID: ', IFNULL(customer_id, ''), '. ',
        'Dispatch Date: ', IFNULL(dispatch_date, ''), '. ',
        'Technician: ', IFNULL(technician, ''), '. ',
        'Service Type: ', IFNULL(service_type, ''), '. ',
        'Hours Spent: ', IFNULL(hours_spent, ''), '. ',
        'Labor Cost: ', IFNULL(labor_cost, ''), '. ',
        'Resolution Summary: ', IFNULL(resolution_summary, ''), '. ',
        'Status: ', IFNULL(status, ''), '.'
    )
) VIRTUAL;


-- Add generated column to warranty_claims table
ALTER TABLE warranty_claims
ADD COLUMN warranty_context TEXT
GENERATED ALWAYS AS (
    CONCAT(
        'Claim ID: ', IFNULL(claim_id, ''), '. ',
        'Equipment ID: ', IFNULL(equipment_id, ''), '. ',
        'Dispatch ID: ', IFNULL(dispatch_id, ''), '. ',
        'Part ID: ', IFNULL(part_id, ''), '. ',
        'Claim Date: ', IFNULL(claim_date, ''), '. ',
        'Claim Amount: ', IFNULL(claim_amount, ''), '. ',
        'Approved Amount: ', IFNULL(approved_amount, ''), '. ',
        'Status: ', IFNULL(status, ''), '. ',
        'Denial Reason: ', IFNULL(denial_reason, ''), '. ',
        'Claim Notes: ', IFNULL(claim_notes, ''), '.'
    )
) VIRTUAL;


-- ============================================================
-- 2. CREATE RAG PAYLOAD TABLE
-- ============================================================

DROP TABLE IF EXISTS rag_payloads;

CREATE TABLE rag_payloads (
    rag_payload_id INT AUTO_INCREMENT PRIMARY KEY,
    source_type VARCHAR(50) NOT NULL,
    source_id VARCHAR(50) NOT NULL,
    equipment_id VARCHAR(50),
    customer_id VARCHAR(50),
    rag_text LONGTEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;


-- ============================================================
-- 3. STORED PROCEDURE TO PREPARE RAG PAYLOADS
-- ============================================================

DELIMITER //

DROP PROCEDURE IF EXISTS sp_Prepare_RAG_Payloads //

CREATE PROCEDURE sp_Prepare_RAG_Payloads()
BEGIN
    -- Clear previous RAG payloads so the procedure can be rerun
    TRUNCATE TABLE rag_payloads;

    -- Create RAG payloads from dispatch/service records
    INSERT INTO rag_payloads (
        source_type,
        source_id,
        equipment_id,
        customer_id,
        rag_text
    )
    SELECT
        'DISPATCH_SERVICE_LOG' AS source_type,
        d.dispatch_id AS source_id,
        d.equipment_id,
        d.customer_id,
        TRIM(
            REGEXP_REPLACE(
                CONCAT(
                    'Service Record. ',
                    'Dispatch ID: ', IFNULL(d.dispatch_id, ''), '. ',
                    'Dispatch Date: ', IFNULL(d.dispatch_date, ''), '. ',
                    'Technician: ', IFNULL(d.technician, ''), '. ',
                    'Service Type: ', IFNULL(d.service_type, ''), '. ',
                    'Status: ', IFNULL(d.status, ''), '. ',
                    'Resolution: ', IFNULL(d.resolution_summary, ''), '. ',
                    'Equipment Model: ', IFNULL(e.model, ''), '. ',
                    'Serial Number: ', IFNULL(e.serial_number, ''), '. ',
                    'Equipment Status: ', IFNULL(e.status, ''), '. ',
                    'Location Notes: ', IFNULL(e.location_notes, ''), '. ',
                    'Customer Company: ', IFNULL(c.company_name, ''), '. '
                ),
                '<[^>]+>',
                ''
            )
        ) AS rag_text
    FROM dispatches d
    LEFT JOIN equipment e
        ON d.equipment_id = e.equipment_id
    LEFT JOIN customers c
        ON d.customer_id = c.customer_id;

    -- Create RAG payloads from warranty claims
    INSERT INTO rag_payloads (
        source_type,
        source_id,
        equipment_id,
        customer_id,
        rag_text
    )
    SELECT
        'WARRANTY_CLAIM' AS source_type,
        wc.claim_id AS source_id,
        wc.equipment_id,
        e.customer_id,
        TRIM(
            REGEXP_REPLACE(
                CONCAT(
                    'Warranty Claim. ',
                    'Claim ID: ', IFNULL(wc.claim_id, ''), '. ',
                    'Claim Date: ', IFNULL(wc.claim_date, ''), '. ',
                    'Claim Amount: ', IFNULL(wc.claim_amount, ''), '. ',
                    'Approved Amount: ', IFNULL(wc.approved_amount, ''), '. ',
                    'Claim Status: ', IFNULL(wc.status, ''), '. ',
                    'Denial Reason: ', IFNULL(wc.denial_reason, ''), '. ',
                    'Claim Notes: ', IFNULL(wc.claim_notes, ''), '. ',
                    'Equipment Model: ', IFNULL(e.model, ''), '. ',
                    'Serial Number: ', IFNULL(e.serial_number, ''), '. ',
                    'Part Name: ', IFNULL(p.part_name, ''), '. ',
                    'Part Category: ', IFNULL(p.category, ''), '. ',
                    'Manufacturer: ', IFNULL(p.manufacturer, ''), '. '
                ),
                '<[^>]+>',
                ''
            )
        ) AS rag_text
    FROM warranty_claims wc
    LEFT JOIN equipment e
        ON wc.equipment_id = e.equipment_id
    LEFT JOIN parts p
        ON wc.part_id = p.part_id;
		
-- Create RAG payloads from equipment records
	INSERT INTO rag_payloads (
		source_type,
		source_id,
		equipment_id,
		customer_id,
		rag_text
	)
	SELECT
		'EQUIPMENT_PROFILE' AS source_type,
		e.equipment_id AS source_id,
		e.equipment_id,
		e.customer_id,
		TRIM(
			REGEXP_REPLACE(
				REGEXP_REPLACE(
					CONCAT(
						'Equipment Profile. ',
						'Equipment ID: ', IFNULL(e.equipment_id, ''), '. ',
						'Customer ID: ', IFNULL(e.customer_id, ''), '. ',
						'Customer Company: ', IFNULL(c.company_name, ''), '. ',
						'Model: ', IFNULL(e.model, ''), '. ',
						'Serial Number: ', IFNULL(e.serial_number, ''), '. ',
						'Install Date: ', IFNULL(e.install_date, ''), '. ',
						'Capacity KW: ', IFNULL(e.capacity_kw, ''), '. ',
						'Voltage: ', IFNULL(e.voltage, ''), '. ',
						'Warranty Expiration: ', IFNULL(e.warranty_expiration, ''), '. ',
						'Equipment Status: ', IFNULL(e.status, ''), '. ',
						'Location Notes: ', IFNULL(e.location_notes, ''), '. '
					),
					'<[^>]+>',
					''
				),
				'[[:space:]]+',
				' '
			)
		) AS rag_text
	FROM equipment e
	LEFT JOIN customers c
		ON e.customer_id = c.customer_id;
		
END //

DELIMITER ;




-- ============================================================
-- 4. AUDIT LOG TABLE
-- ============================================================

DROP TABLE IF EXISTS audit_logs;

CREATE TABLE audit_logs (
    audit_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    table_name VARCHAR(100) NOT NULL,
    operation_type VARCHAR(20) NOT NULL,
    record_id VARCHAR(100) NOT NULL,
    old_values LONGTEXT,
    new_values LONGTEXT,
    changed_by VARCHAR(100) DEFAULT CURRENT_USER(),
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    change_description VARCHAR(255)
) ENGINE=InnoDB;


-- ============================================================
-- 5. MAKE AUDIT LOG IMMUTABLE
-- Prevent users from updating or deleting audit records
-- ============================================================

DELIMITER //

DROP TRIGGER IF EXISTS trg_audit_logs_no_update //

CREATE TRIGGER trg_audit_logs_no_update
BEFORE UPDATE ON audit_logs
FOR EACH ROW
BEGIN
    SIGNAL SQLSTATE '45000'
    SET MESSAGE_TEXT = 'Audit logs are immutable and cannot be updated.';
END //

DROP TRIGGER IF EXISTS trg_audit_logs_no_delete //

CREATE TRIGGER trg_audit_logs_no_delete
BEFORE DELETE ON audit_logs
FOR EACH ROW
BEGIN
    SIGNAL SQLSTATE '45000'
    SET MESSAGE_TEXT = 'Audit logs are immutable and cannot be deleted.';
END //

DELIMITER ;


-- ============================================================
-- 6. AUDIT TRIGGERS FOR CUSTOMERS
-- ============================================================

DELIMITER //

DROP TRIGGER IF EXISTS trg_customers_after_insert //

CREATE TRIGGER trg_customers_after_insert
AFTER INSERT ON customers
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (
        table_name,
        operation_type,
        record_id,
        old_values,
        new_values,
        change_description
    )
    VALUES (
        'customers',
        'INSERT',
        NEW.customer_id,
        NULL,
        JSON_OBJECT(
            'customer_id', NEW.customer_id,
            'company_name', NEW.company_name,
            'contact_name', NEW.contact_name,
            'phone', NEW.phone,
            'email', NEW.email,
            'address', NEW.address,
            'zip', NEW.zip,
            'created_date', NEW.created_date,
            'status', NEW.status
        ),
        'New customer record created'
    );
END //

DROP TRIGGER IF EXISTS trg_customers_before_update //

CREATE TRIGGER trg_customers_before_update
BEFORE UPDATE ON customers
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (
        table_name,
        operation_type,
        record_id,
        old_values,
        new_values,
        change_description
    )
    VALUES (
        'customers',
        'UPDATE',
        OLD.customer_id,
        JSON_OBJECT(
            'customer_id', OLD.customer_id,
            'company_name', OLD.company_name,
            'contact_name', OLD.contact_name,
            'phone', OLD.phone,
            'email', OLD.email,
            'address', OLD.address,
            'zip', OLD.zip,
            'created_date', OLD.created_date,
            'status', OLD.status
        ),
        JSON_OBJECT(
            'customer_id', NEW.customer_id,
            'company_name', NEW.company_name,
            'contact_name', NEW.contact_name,
            'phone', NEW.phone,
            'email', NEW.email,
            'address', NEW.address,
            'zip', NEW.zip,
            'created_date', NEW.created_date,
            'status', NEW.status
        ),
        'Customer record updated'
    );
END //

DELIMITER ;

-- ============================================================
-- AUDIT TRIGGERS FOR WARRANTY CLAIMS
-- ============================================================

DELIMITER //

DROP TRIGGER IF EXISTS trg_warranty_claims_after_insert //

CREATE TRIGGER trg_warranty_claims_after_insert
AFTER INSERT ON warranty_claims
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (
        table_name,
        operation_type,
        record_id,
        old_values,
        new_values,
        change_description
    )
    VALUES (
        'warranty_claims',
        'INSERT',
        NEW.claim_id,
        NULL,
        JSON_OBJECT(
            'claim_id', NEW.claim_id,
            'equipment_id', NEW.equipment_id,
            'dispatch_id', NEW.dispatch_id,
            'part_id', NEW.part_id,
            'claim_date', NEW.claim_date,
            'claim_amount', NEW.claim_amount,
            'approved_amount', NEW.approved_amount,
            'status', NEW.status,
            'denial_reason', NEW.denial_reason,
            'claim_notes', NEW.claim_notes
        ),
        'New warranty claim record created'
    );
END //

DROP TRIGGER IF EXISTS trg_warranty_claims_before_update //

CREATE TRIGGER trg_warranty_claims_before_update
BEFORE UPDATE ON warranty_claims
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (
        table_name,
        operation_type,
        record_id,
        old_values,
        new_values,
        change_description
    )
    VALUES (
        'warranty_claims',
        'UPDATE',
        OLD.claim_id,
        JSON_OBJECT(
            'claim_id', OLD.claim_id,
            'equipment_id', OLD.equipment_id,
            'dispatch_id', OLD.dispatch_id,
            'part_id', OLD.part_id,
            'claim_date', OLD.claim_date,
            'claim_amount', OLD.claim_amount,
            'approved_amount', OLD.approved_amount,
            'status', OLD.status,
            'denial_reason', OLD.denial_reason,
            'claim_notes', OLD.claim_notes
        ),
        JSON_OBJECT(
            'claim_id', NEW.claim_id,
            'equipment_id', NEW.equipment_id,
            'dispatch_id', NEW.dispatch_id,
            'part_id', NEW.part_id,
            'claim_date', NEW.claim_date,
            'claim_amount', NEW.claim_amount,
            'approved_amount', NEW.approved_amount,
            'status', NEW.status,
            'denial_reason', NEW.denial_reason,
            'claim_notes', NEW.claim_notes
        ),
        'Warranty claim record updated'
    );
END //

DELIMITER ;


-- ============================================================
-- 7. AUDIT TRIGGERS FOR EQUIPMENT
-- ============================================================

DELIMITER //

DROP TRIGGER IF EXISTS trg_equipment_after_insert //

CREATE TRIGGER trg_equipment_after_insert
AFTER INSERT ON equipment
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (
        table_name,
        operation_type,
        record_id,
        old_values,
        new_values,
        change_description
    )
    VALUES (
        'equipment',
        'INSERT',
        NEW.equipment_id,
        NULL,
        JSON_OBJECT(
            'equipment_id', NEW.equipment_id,
            'customer_id', NEW.customer_id,
            'model', NEW.model,
            'serial_number', NEW.serial_number,
            'install_date', NEW.install_date,
            'capacity_kw', NEW.capacity_kw,
            'voltage', NEW.voltage,
            'warranty_expiration', NEW.warranty_expiration,
            'status', NEW.status,
            'location_notes', NEW.location_notes
        ),
        'New equipment record created'
    );
END //

DROP TRIGGER IF EXISTS trg_equipment_before_update //

CREATE TRIGGER trg_equipment_before_update
BEFORE UPDATE ON equipment
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (
        table_name,
        operation_type,
        record_id,
        old_values,
        new_values,
        change_description
    )
    VALUES (
        'equipment',
        'UPDATE',
        OLD.equipment_id,
        JSON_OBJECT(
            'equipment_id', OLD.equipment_id,
            'customer_id', OLD.customer_id,
            'model', OLD.model,
            'serial_number', OLD.serial_number,
            'install_date', OLD.install_date,
            'capacity_kw', OLD.capacity_kw,
            'voltage', OLD.voltage,
            'warranty_expiration', OLD.warranty_expiration,
            'status', OLD.status,
            'location_notes', OLD.location_notes
        ),
        JSON_OBJECT(
            'equipment_id', NEW.equipment_id,
            'customer_id', NEW.customer_id,
            'model', NEW.model,
            'serial_number', NEW.serial_number,
            'install_date', NEW.install_date,
            'capacity_kw', NEW.capacity_kw,
            'voltage', NEW.voltage,
            'warranty_expiration', NEW.warranty_expiration,
            'status', NEW.status,
            'location_notes', NEW.location_notes
        ),
        'Equipment record updated'
    );
END //

DELIMITER ;


-- ============================================================
-- 8. AUDIT TRIGGERS FOR DISPATCHES / SERVICE LOGS
-- ============================================================

DELIMITER //

DROP TRIGGER IF EXISTS trg_dispatches_after_insert //

CREATE TRIGGER trg_dispatches_after_insert
AFTER INSERT ON dispatches
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (
        table_name,
        operation_type,
        record_id,
        old_values,
        new_values,
        change_description
    )
    VALUES (
        'dispatches',
        'INSERT',
        NEW.dispatch_id,
        NULL,
        JSON_OBJECT(
            'dispatch_id', NEW.dispatch_id,
            'equipment_id', NEW.equipment_id,
            'customer_id', NEW.customer_id,
            'dispatch_date', NEW.dispatch_date,
            'technician', NEW.technician,
            'service_type', NEW.service_type,
            'hours_spent', NEW.hours_spent,
            'labor_cost', NEW.labor_cost,
            'resolution_summary', NEW.resolution_summary,
            'status', NEW.status
        ),
        'New dispatch/service record created'
    );
END //

DROP TRIGGER IF EXISTS trg_dispatches_before_update //

CREATE TRIGGER trg_dispatches_before_update
BEFORE UPDATE ON dispatches
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (
        table_name,
        operation_type,
        record_id,
        old_values,
        new_values,
        change_description
    )
    VALUES (
        'dispatches',
        'UPDATE',
        OLD.dispatch_id,
        JSON_OBJECT(
            'dispatch_id', OLD.dispatch_id,
            'equipment_id', OLD.equipment_id,
            'customer_id', OLD.customer_id,
            'dispatch_date', OLD.dispatch_date,
            'technician', OLD.technician,
            'service_type', OLD.service_type,
            'hours_spent', OLD.hours_spent,
            'labor_cost', OLD.labor_cost,
            'resolution_summary', OLD.resolution_summary,
            'status', OLD.status
        ),
        JSON_OBJECT(
            'dispatch_id', NEW.dispatch_id,
            'equipment_id', NEW.equipment_id,
            'customer_id', NEW.customer_id,
            'dispatch_date', NEW.dispatch_date,
            'technician', NEW.technician,
            'service_type', NEW.service_type,
            'hours_spent', NEW.hours_spent,
            'labor_cost', NEW.labor_cost,
            'resolution_summary', NEW.resolution_summary,
            'status', NEW.status
        ),
        'Dispatch/service record updated'
    );
END //

DELIMITER ;


-- ============================================================
-- 9. SECURITY VIEWS
-- Hide sensitive customer phone, email, and address
-- ============================================================

DROP VIEW IF EXISTS vw_customer_safe;

CREATE VIEW vw_customer_safe AS
SELECT
    c.customer_id,
    c.company_name,
    c.contact_name,
    CONCAT('***-***-', RIGHT(c.phone, 4)) AS masked_phone,
    CONCAT(
        LEFT(c.email, 2),
        '***@',
        SUBSTRING_INDEX(c.email, '@', -1)
    ) AS masked_email,
    c.zip,
    l.city,
    l.state,
    l.country,
    c.created_date,
    c.status
FROM customers c
LEFT JOIN locations l
    ON c.zip = l.zip;


DROP VIEW IF EXISTS vw_rag_service_context;

CREATE VIEW vw_rag_service_context AS
SELECT
    d.dispatch_id,
    d.equipment_id,
    d.customer_id,
    e.model,
    e.serial_number,
    d.dispatch_date,
    d.technician,
    d.service_type,
    d.status,
    CONCAT(
        e.equipment_context,
        ' ',
        d.service_context
    ) AS full_service_context
FROM dispatches d
LEFT JOIN equipment e
    ON d.equipment_id = e.equipment_id;
	
-- ============================================================
-- SECURITY VIEW FOR WARRANTY CLAIMS
-- ============================================================

DROP VIEW IF EXISTS vw_warranty_claims_safe;

CREATE VIEW vw_warranty_claims_safe AS
SELECT
    wc.claim_id,
    wc.equipment_id,
    wc.dispatch_id,
    wc.part_id,
    wc.claim_date,

    -- Mask financial details for non-privileged users
    CASE
        WHEN wc.claim_amount IS NULL THEN NULL
        ELSE 'REDACTED'
    END AS claim_amount_masked,

    CASE
        WHEN wc.approved_amount IS NULL THEN NULL
        ELSE 'REDACTED'
    END AS approved_amount_masked,

    wc.status,

    -- Hide detailed denial reason and claim notes
    CASE
        WHEN wc.denial_reason IS NULL OR wc.denial_reason = '' THEN 'Not provided'
        ELSE 'Restricted'
    END AS denial_reason_summary,

    CASE
        WHEN wc.claim_notes IS NULL OR wc.claim_notes = '' THEN 'No claim notes'
        ELSE 'Restricted'
    END AS claim_notes_summary,

    e.model AS equipment_model,
    e.serial_number,
    e.status AS equipment_status
FROM warranty_claims wc
LEFT JOIN equipment e
    ON wc.equipment_id = e.equipment_id;


-- Optional restricted analyst user example
-- Change the password before using in a real environment

DROP USER IF EXISTS 'gigavolt_analyst'@'%';

CREATE USER 'gigavolt_analyst'@'%' IDENTIFIED BY 'ChangeThisPassword123!';

GRANT SELECT ON gigavolt_erp.vw_customer_safe TO 'gigavolt_analyst'@'%';
GRANT SELECT ON gigavolt_erp.vw_rag_service_context TO 'gigavolt_analyst'@'%';
GRANT SELECT ON gigavolt_erp.rag_payloads TO 'gigavolt_analyst'@'%';
GRANT SELECT ON gigavolt_erp.vw_warranty_claims_safe TO 'gigavolt_analyst'@'%';
-- Do NOT grant direct SELECT on customers to this user.
-- This proves sensitive customer data is protected.

FLUSH PRIVILEGES;




-- ============================================================
-- 10. TEST QUERIES FOR YOUR VIDEO DEMO
-- ============================================================

-- Run the stored procedure
CALL sp_Prepare_RAG_Payloads();

-- Show RAG-ready output
SELECT *
FROM rag_payloads
LIMIT 5;

-- Show generated service context
SELECT dispatch_id, service_context
FROM dispatches
LIMIT 5;

-- Test AFTER INSERT trigger
INSERT INTO customers (
    customer_id,
    company_name,
    contact_name,
    phone,
    email,
    address,
    zip,
    created_date,
    status
)
VALUES (
    'CUST_TEST_001',
    'Test Battery Company',
    'Jane Test',
    '555-111-2222',
    'jane.test@example.com',
    '123 Test Street',
    (SELECT zip FROM locations LIMIT 1),
    CURRENT_DATE,
    'ACTIVE'
);

-- Test BEFORE UPDATE trigger
UPDATE customers
SET status = 'INACTIVE'
WHERE customer_id = 'CUST_TEST_001';

-- Verify audit logs
SELECT *
FROM audit_logs
ORDER BY changed_at DESC
LIMIT 10;

-- Verify security view hides sensitive information
SELECT *
FROM vw_customer_safe
LIMIT 10;
