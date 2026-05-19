
CREATE TABLE Hospital (
    h_ID        VARCHAR(10)  NOT NULL,
    h_name      VARCHAR(100) NOT NULL,
    h_address      VARCHAR(50)  NOT NULL,
    PRIMARY KEY (h_ID)
);

CREATE TABLE Distributor (
    d_ID        VARCHAR(10)  NOT NULL,
    d_name      VARCHAR(100) NOT NULL,
    d_address   VARCHAR(200) NOT NULL,
    d_password INT NOT NULL,
    PRIMARY KEY (d_ID)
);

CREATE TABLE Medicine (
    m_ID        VARCHAR(20)  NOT NULL,
    m_name      VARCHAR(100) NOT NULL,
    unit_price  DECIMAL(10,2) NOT NULL,
    manufacturer VARCHAR(100) NOT NULL,
    PRIMARY KEY (m_ID)
);

CREATE TABLE Doctor (
    dc_ID         VARCHAR(10)  NOT NULL,
    dc_first_name       VARCHAR(50) NOT NULL, 
    dc_last_name	VARCHAR(50) NOT NULL,
    dc_department VARCHAR(50) NOT NULL,
    dc_phone1      VARCHAR(20)  NOT NULL,
    dc_phone2      VARCHAR(20)  NOT NULL,
    dc_password    INT NOT NULL,
    h_ID          VARCHAR(10)  NOT NULL,
    PRIMARY KEY (dc_ID),
    FOREIGN KEY (h_ID) REFERENCES Hospital(h_ID) ON DELETE CASCADE
);

CREATE TABLE Patient (
    pat_ID       VARCHAR(10)  NOT NULL,
    pat_name     VARCHAR(100) NOT NULL,
    pat_age      INT          NOT NULL,
    pat_gender   ENUM('M','F') NOT NULL,
    pat_department  VARCHAR(100), 
    pat_allergy  VARCHAR(200),
    dc_ID VARCHAR(10) NOT NULL,
    PRIMARY KEY (pat_ID),
    FOREIGN KEY (dc_ID) REFERENCES Doctor(dc_ID)
);

CREATE TABLE Pharmacy (
    p_ID        VARCHAR(10)  NOT NULL,
    p_phone     VARCHAR(20)  NOT NULL,
    p_location  VARCHAR(200) NOT NULL,  
    h_ID        VARCHAR(10)  NOT NULL,
    p_type  VARCHAR(20) NOT NULL,
    PRIMARY KEY (p_ID),
    FOREIGN KEY (h_ID) REFERENCES Hospital(h_ID) ON DELETE CASCADE
);

CREATE TABLE Pharmacist (
    p_ID        VARCHAR(10)  NOT NULL,
    ph_name     VARCHAR(100) NOT NULL,
    ph_ID       VARCHAR(10)  NOT NULL,
    ph_phone1    VARCHAR(20)  NOT NULL,
    ph_phone2    VARCHAR(20)  NOT NULL,
    ph_password  INT NOT NULL,
    PRIMARY KEY (ph_ID),
    FOREIGN KEY (p_ID) REFERENCES Pharmacy(p_ID) ON DELETE CASCADE
);

CREATE TABLE Medicine_Batch (
    mb_ID           VARCHAR(20)  NOT NULL,
    m_ID            VARCHAR(20)  NOT NULL,
    production_date DATE         NOT NULL,
    expiration_date DATE         NOT NULL,
    PRIMARY KEY (mb_ID),
    FOREIGN KEY (m_ID) REFERENCES Medicine(m_ID) ON DELETE CASCADE
);

CREATE TABLE Hospital_Order (
    ho_ID       VARCHAR(10)  NOT NULL,
    h_ID        VARCHAR(10)  NOT NULL,
    ho_date     DATE         NOT NULL,
    ho_status   VARCHAR(50)  NOT NULL,
    d_ID        VARCHAR(10)  NOT NULL,
    PRIMARY KEY (ho_ID),
    FOREIGN KEY (h_ID) REFERENCES Hospital(h_ID),
    FOREIGN KEY (d_ID) REFERENCES Distributor(d_ID)
);

CREATE TABLE Prescription (
    pr_ID           VARCHAR(20)  NOT NULL,
    pr_date         DATE         NOT NULL,
    pr_symptom   VARCHAR(100) NOT NULL,
    pat_ID           VARCHAR(20)  NOT NULL,
    dc_ID           VARCHAR(10)  NOT NULL,
    ph_ID       VARCHAR(10)  NOT NULL,
    PRIMARY KEY (pr_ID),
    FOREIGN KEY (dc_ID) REFERENCES Doctor(dc_ID),
    FOREIGN KEY (pat_ID) REFERENCES Patient(pat_ID),
    FOREIGN KEY (ph_ID) REFERENCES Pharmacist(ph_ID)
);

CREATE TABLE Payment (
    py_ID       VARCHAR(20)   NOT NULL,
    pr_ID       VARCHAR(20)   NOT NULL,
    price       DECIMAL(10,2) NOT NULL,
    py_status   ENUM('paid','unpaid','delayed') NOT NULL DEFAULT 'unpaid',
    py_date         DATE ,
    PRIMARY KEY (py_ID),
    FOREIGN KEY (pr_ID) REFERENCES Prescription(pr_ID) ON DELETE CASCADE
);

CREATE TABLE Contain (
    pr_ID       VARCHAR(20)  NOT NULL,
    m_ID        VARCHAR(20)  NOT NULL,
    quantity    INT          NOT NULL,
    PRIMARY KEY (pr_ID, m_ID),
    FOREIGN KEY (pr_ID) REFERENCES Prescription(pr_ID) ON DELETE CASCADE,
    FOREIGN KEY (m_ID)  REFERENCES Medicine(m_ID)
);

CREATE TABLE Store (
    s_ID                VARCHAR(10)  NOT NULL,
    p_ID                VARCHAR(10)  NOT NULL,
    inventory           INT          NOT NULL DEFAULT 0,
    store_date          DATE         NOT NULL,
    m_ID                VARCHAR(20)  NOT NULL,
    PRIMARY KEY (s_ID),
    FOREIGN KEY (p_ID) REFERENCES Pharmacy(p_ID),
    FOREIGN KEY (m_ID) REFERENCES Medicine(m_ID)
);

CREATE TABLE Supply(
ho_ID       VARCHAR(10)  NOT NULL,
quantity   VARCHAR(10) NOT NULL,
p_ID        VARCHAR(10)  NOT NULL,
su_ID      VARCHAR(10) NOT NULL,
PRIMARY KEY (su_ID),
FOREIGN KEY (p_ID) REFERENCES Pharmacy(p_ID) ON DELETE CASCADE,
FOREIGN KEY (ho_ID) REFERENCES Hospital_Order(ho_ID)
);

CREATE TABLE admin（
admin_ID VARCHAR(20) NOT NULL,
admin_name VARCHAR(50) NOT NULL,
admin_password VARCHAR(100) NOT NULL,
PRIMARY KEY (admin_ID));


-- =====================================
-- INDEXES
-- =====================================

-- Speed up patient name search
CREATE INDEX idx_patient_name
ON Patient(pat_name);

-- Speed up doctor prescription lookup
CREATE INDEX idx_prescription_doctor
ON Prescription(dc_ID);

-- Speed up patient prescription lookup
CREATE INDEX idx_prescription_patient
ON Prescription(pat_ID);

-- Speed up medicine name search
CREATE INDEX idx_medicine_name
ON Medicine(m_name);

-- Speed up expiration date query
CREATE INDEX idx_batch_expiration
ON Medicine_Batch(expiration_date);

-- Speed up inventory lookup
CREATE INDEX idx_store_medicine
ON Store(m_ID);

-- Prevent prescription when stock is insufficient

DELIMITER //

CREATE TRIGGER trg_check_stock
BEFORE INSERT ON Contain
FOR EACH ROW
BEGIN

    DECLARE current_stock INT;

    SELECT inventory
    INTO current_stock
    FROM Store
    WHERE m_ID = NEW.m_ID
    LIMIT 1;

    IF current_stock < NEW.quantity THEN

        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Cannot prescribe: insufficient stock';

    END IF;

END //

DELIMITER ;

-- Automatically reduce inventory after prescription

DELIMITER //

CREATE TRIGGER trg_reduce_inventory
AFTER INSERT ON Contain
FOR EACH ROW
BEGIN

    UPDATE Store
    SET inventory = inventory - NEW.quantity
    WHERE m_ID = NEW.m_ID;

END //

DELIMITER ;

-- Validate medicine batch expiration date

DELIMITER //

CREATE TRIGGER trg_check_expiry
BEFORE INSERT ON Medicine_Batch
FOR EACH ROW
BEGIN

    IF NEW.expiration_date <= NEW.production_date THEN

        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Expiration date must be after production date';

    END IF;

    IF NEW.expiration_date < CURDATE() THEN

        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Medicine batch already expired';

    END IF;

END //

DELIMITER ;

