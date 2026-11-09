-- =============================================================================
-- ENTERPRISE EMPLOYEE ANALYTICS & DATA WAREHOUSE SYSTEM
-- Master SQL file | MySQL 8.0+
--
-- Databases:
--   1. hr_staging : imported CSV data
--   2. hr_oltp    : normalized operational data
--   3. hr_dw      : dimensional data warehouse
--
-- IMPORTANT EXECUTION WORKFLOW
--   A. Execute Sections 1-2 to create databases and staging tables.
--   B. Import the five CSV files into the matching staging tables using
--      MySQL Workbench's Table Data Import Wizard.
--   C. Execute Section 3 to populate normalized OLTP tables.
--   D. Execute Section 4 to create/populate warehouse dimensions and facts.
--
-- Run this file on MySQL 8.0+. It is designed to be rerunnable for table
-- creation, but data-loading INSERT statements should be reviewed before
-- rerunning to avoid duplicate or unintended data.
--
-- Source assumptions confirmed by the team:
--   * EmployeeNumber is consistent across all five CSV files.
--   * One assignment row exists per employee-project pair.
--   * Salary history is represented in employee_scd2_history.csv and
--     Dim_Employee SCD Type 2; no separate OLTP Salary_History table.
-- =============================================================================


-- =============================================================================
-- SECTION 1: DATABASES
-- =============================================================================

CREATE DATABASE IF NOT EXISTS hr_staging
    CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE DATABASE IF NOT EXISTS hr_oltp
    CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE DATABASE IF NOT EXISTS hr_dw
    CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;


-- =============================================================================
-- SECTION 2: STAGING TABLES
-- Purpose: preserve incoming CSV data before normalization/transformation.
--
-- Import mapping:
--   employee_snapshot.csv       -> hr_staging.stg_employee_snapshot
--   employee_scd2_history.csv   -> hr_staging.stg_employee_scd2_history
--   performance_reviews.csv     -> hr_staging.stg_performance_reviews
--   project_assignments.csv     -> hr_staging.stg_project_assignments
--   projects.csv                -> hr_staging.stg_projects
--
-- The staging tables use source-oriented names. If your CSV headers differ
-- slightly, map the CSV columns to these fields in the import wizard.
-- =============================================================================

USE hr_staging;

CREATE TABLE IF NOT EXISTS stg_employee_snapshot (
    age                         TINYINT UNSIGNED,
    attrition                   VARCHAR(5),
    business_travel             VARCHAR(30),
    daily_rate                  SMALLINT UNSIGNED,
    department                  VARCHAR(100),
    distance_from_home          TINYINT UNSIGNED,
    education                   TINYINT UNSIGNED,
    education_field             VARCHAR(100),
    employee_number             INT NOT NULL,
    environment_satisfaction    TINYINT UNSIGNED,
    gender                      VARCHAR(20),
    hourly_rate                 TINYINT UNSIGNED,
    job_involvement             TINYINT UNSIGNED,
    job_level                   TINYINT UNSIGNED,
    job_role                    VARCHAR(100),
    job_satisfaction            TINYINT UNSIGNED,
    marital_status              VARCHAR(30),
    monthly_income              DECIMAL(12,2),
    monthly_rate                INT UNSIGNED,
    num_companies_worked        TINYINT UNSIGNED,
    overtime                    VARCHAR(5),
    percent_salary_hike         TINYINT UNSIGNED,
    performance_rating          TINYINT UNSIGNED,
    relationship_satisfaction   TINYINT UNSIGNED,
    stock_option_level          TINYINT UNSIGNED,
    total_working_years         TINYINT UNSIGNED,
    training_times_last_year    TINYINT UNSIGNED,
    work_life_balance           TINYINT UNSIGNED,
    years_at_company            TINYINT UNSIGNED,
    years_in_current_role       TINYINT UNSIGNED,
    years_since_last_promotion  TINYINT UNSIGNED,
    years_with_curr_manager     TINYINT UNSIGNED,
    synthetic_employee_name     VARCHAR(150),
    synthetic_employee_email    VARCHAR(255),
    synthetic_hire_date         DATE,
    PRIMARY KEY (employee_number),
    INDEX idx_stg_snapshot_department (department),
    INDEX idx_stg_snapshot_job_role (job_role)
) ENGINE=InnoDB;


CREATE TABLE IF NOT EXISTS stg_employee_scd2_history (
    age                         TINYINT UNSIGNED,
    attrition                   VARCHAR(5),
    business_travel             VARCHAR(30),
    daily_rate                  SMALLINT UNSIGNED,
    department                  VARCHAR(100),
    distance_from_home          TINYINT UNSIGNED,
    education                   TINYINT UNSIGNED,
    education_field             VARCHAR(100),
    employee_number             INT NOT NULL,
    environment_satisfaction    TINYINT UNSIGNED,
    gender                      VARCHAR(20),
    hourly_rate                 TINYINT UNSIGNED,
    job_involvement             TINYINT UNSIGNED,
    job_level                   TINYINT UNSIGNED,
    job_role                    VARCHAR(100),
    job_satisfaction            TINYINT UNSIGNED,
    marital_status              VARCHAR(30),
    monthly_income              DECIMAL(12,2),
    monthly_rate                INT UNSIGNED,
    num_companies_worked        TINYINT UNSIGNED,
    overtime                    VARCHAR(5),
    percent_salary_hike         TINYINT UNSIGNED,
    performance_rating          TINYINT UNSIGNED,
    relationship_satisfaction   TINYINT UNSIGNED,
    stock_option_level          TINYINT UNSIGNED,
    total_working_years         TINYINT UNSIGNED,
    training_times_last_year    TINYINT UNSIGNED,
    work_life_balance           TINYINT UNSIGNED,
    years_at_company            TINYINT UNSIGNED,
    years_in_current_role       TINYINT UNSIGNED,
    years_since_last_promotion  TINYINT UNSIGNED,
    years_with_curr_manager     TINYINT UNSIGNED,
    synthetic_employee_name     VARCHAR(150),
    synthetic_employee_email    VARCHAR(255),
    synthetic_hire_date         DATE,
    start_date                  DATE NOT NULL,
    end_date                    DATE NOT NULL,
    is_current                  BOOLEAN NOT NULL,
    change_reason               VARCHAR(100),
    INDEX idx_stg_history_employee (employee_number),
    INDEX idx_stg_history_dates (start_date, end_date),
    INDEX idx_stg_history_current (employee_number, is_current)
) ENGINE=InnoDB;


CREATE TABLE IF NOT EXISTS stg_performance_reviews (
    review_id           INT NOT NULL,
    employee_number     INT NOT NULL,
    project_id          INT NOT NULL,
    review_date         DATE NOT NULL,
    review_year         SMALLINT NOT NULL,
    performance_rating  TINYINT UNSIGNED,
    job_satisfaction    TINYINT UNSIGNED,
    review_score        DECIMAL(5,2),
    PRIMARY KEY (review_id),
    INDEX idx_stg_review_employee (employee_number),
    INDEX idx_stg_review_project (project_id),
    INDEX idx_stg_review_date (review_date)
) ENGINE=InnoDB;


CREATE TABLE IF NOT EXISTS stg_project_assignments (
    assignment_id   INT NOT NULL,
    employee_number INT NOT NULL,
    project_id      INT NOT NULL,
    is_primary      BOOLEAN NOT NULL,
    assigned_date   DATE NOT NULL,
    allocation_pct  DECIMAL(5,2) NOT NULL,
    PRIMARY KEY (assignment_id),
    UNIQUE KEY uq_stg_employee_project (employee_number, project_id),
    INDEX idx_stg_assignment_project (project_id)
) ENGINE=InnoDB;


CREATE TABLE IF NOT EXISTS stg_projects (
    project_id      INT NOT NULL,
    project_name    VARCHAR(150) NOT NULL,
    department      VARCHAR(100) NOT NULL,
    start_date      DATE NOT NULL,
    end_date        DATE NULL,
    status          VARCHAR(30) NOT NULL,
    budget          DECIMAL(15,2),
    PRIMARY KEY (project_id),
    INDEX idx_stg_projects_department (department)
) ENGINE=InnoDB;


-- =============================================================================
-- SECTION 3: OLTP NORMALIZED DATABASE
-- Data model:
--   departments 1 --- many employees
--   job_roles   1 --- many employees
--   employees   1 --- many assignments
--   projects    1 --- many assignments
--   employees   1 --- many performance_reviews
--   projects    1 --- many performance_reviews
--
-- EmployeeNumber is retained as a UNIQUE source/business key. employee_id is
-- the OLTP surrogate primary key used by foreign keys.
-- =============================================================================

USE hr_oltp;

CREATE TABLE IF NOT EXISTS departments (
    department_id    INT AUTO_INCREMENT PRIMARY KEY,
    department_name  VARCHAR(100) NOT NULL,
    UNIQUE KEY uq_department_name (department_name)
) ENGINE=InnoDB;


CREATE TABLE IF NOT EXISTS job_roles (
    job_role_id  INT AUTO_INCREMENT PRIMARY KEY,
    job_title    VARCHAR(100) NOT NULL,
    UNIQUE KEY uq_job_title (job_title)
) ENGINE=InnoDB;


CREATE TABLE IF NOT EXISTS employees (
    employee_id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    employee_number          INT NOT NULL,
    first_name               VARCHAR(100) NULL,
    last_name                VARCHAR(100) NULL,
    employee_name            VARCHAR(150) NOT NULL,
    email                    VARCHAR(255) NOT NULL,
    age                      TINYINT UNSIGNED,
    gender                   VARCHAR(20),
    marital_status           VARCHAR(30),
    education                TINYINT UNSIGNED,
    education_field          VARCHAR(100),
    department_id            INT NOT NULL,
    job_role_id              INT NOT NULL,
    job_level                TINYINT UNSIGNED,
    hire_date                DATE,
    attrition                VARCHAR(5),
    business_travel          VARCHAR(30),
    daily_rate               SMALLINT UNSIGNED,
    distance_from_home       TINYINT UNSIGNED,
    environment_satisfaction TINYINT UNSIGNED,
    hourly_rate              TINYINT UNSIGNED,
    job_involvement          TINYINT UNSIGNED,
    job_satisfaction         TINYINT UNSIGNED,
    monthly_income           DECIMAL(12,2),
    monthly_rate             INT UNSIGNED,
    num_companies_worked     TINYINT UNSIGNED,
    overtime                 VARCHAR(5),
    percent_salary_hike      TINYINT UNSIGNED,
    performance_rating      TINYINT UNSIGNED,
    relationship_satisfaction TINYINT UNSIGNED,
    stock_option_level       TINYINT UNSIGNED,
    total_working_years      TINYINT UNSIGNED,
    training_times_last_year TINYINT UNSIGNED,
    work_life_balance        TINYINT UNSIGNED,
    years_at_company         TINYINT UNSIGNED,
    years_in_current_role    TINYINT UNSIGNED,
    years_since_last_promotion TINYINT UNSIGNED,
    years_with_curr_manager  TINYINT UNSIGNED,
    employment_status        VARCHAR(20) NOT NULL DEFAULT 'Active',
    manager_id               BIGINT NULL,
    created_at               TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at               TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                                      ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_employee_number (employee_number),
    UNIQUE KEY uq_employee_email (email),
    INDEX idx_employee_department (department_id),
    INDEX idx_employee_job_role (job_role_id),
    CONSTRAINT fk_employee_department
        FOREIGN KEY (department_id) REFERENCES departments(department_id),
    CONSTRAINT fk_employee_job_role
        FOREIGN KEY (job_role_id) REFERENCES job_roles(job_role_id),
    CONSTRAINT fk_employee_manager
        FOREIGN KEY (manager_id) REFERENCES employees(employee_id)
        ON DELETE SET NULL,
    CONSTRAINT chk_employee_status
        CHECK (employment_status IN ('Active', 'Inactive', 'Terminated'))
) ENGINE=InnoDB;


CREATE TABLE IF NOT EXISTS projects (
    project_id      INT PRIMARY KEY,
    project_name    VARCHAR(150) NOT NULL,
    department_id   INT NOT NULL,
    start_date      DATE NOT NULL,
    end_date        DATE NULL,
    project_status  VARCHAR(30) NOT NULL,
    budget          DECIMAL(15,2),
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                             ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_project_department (department_id),
    INDEX idx_project_status (project_status),
    CONSTRAINT fk_project_department
        FOREIGN KEY (department_id) REFERENCES departments(department_id),
    CONSTRAINT chk_project_dates
        CHECK (end_date IS NULL OR end_date >= start_date),
    CONSTRAINT chk_project_budget
        CHECK (budget IS NULL OR budget >= 0)
) ENGINE=InnoDB;


CREATE TABLE IF NOT EXISTS assignments (
    assignment_id    INT PRIMARY KEY,
    employee_id      BIGINT NOT NULL,
    project_id       INT NOT NULL,
    is_primary       BOOLEAN NOT NULL DEFAULT FALSE,
    assigned_date    DATE NOT NULL,
    allocation_pct   DECIMAL(5,2) NOT NULL,
    created_at       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_employee_project (employee_id, project_id),
    INDEX idx_assignment_project (project_id),
    CONSTRAINT fk_assignment_employee
        FOREIGN KEY (employee_id) REFERENCES employees(employee_id),
    CONSTRAINT fk_assignment_project
        FOREIGN KEY (project_id) REFERENCES projects(project_id),
    CONSTRAINT chk_assignment_allocation
        CHECK (allocation_pct > 0 AND allocation_pct <= 100)
) ENGINE=InnoDB;


CREATE TABLE IF NOT EXISTS performance_reviews (
    review_id           INT PRIMARY KEY,
    employee_id         BIGINT NOT NULL,
    project_id          INT NOT NULL,
    review_date         DATE NOT NULL,
    review_year         SMALLINT NOT NULL,
    performance_rating  TINYINT UNSIGNED,
    job_satisfaction    TINYINT UNSIGNED,
    review_score        DECIMAL(5,2),
    created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_review_employee_date (employee_id, review_date),
    INDEX idx_review_project (project_id),
    CONSTRAINT fk_review_employee
        FOREIGN KEY (employee_id) REFERENCES employees(employee_id),
    CONSTRAINT fk_review_project
        FOREIGN KEY (project_id) REFERENCES projects(project_id),
    CONSTRAINT chk_review_score
        CHECK (review_score IS NULL OR (review_score >= 0 AND review_score <= 100))
) ENGINE=InnoDB;


-- =============================================================================
-- SECTION 3A: LOAD NORMALIZED OLTP DATA FROM STAGING
--
-- Execute this section only AFTER importing all five CSV files into staging.
-- The inserts use NOT EXISTS / duplicate-key handling to reduce duplicate
-- loads. Review the staging data and row counts before running.
--
-- Note: The source snapshot does not show manager identifiers, so manager_id
-- remains NULL until a valid manager mapping is supplied.
-- =============================================================================

-- Populate departments from both employee snapshot and project source.
INSERT INTO departments (department_name)
SELECT DISTINCT TRIM(department)
FROM hr_staging.stg_employee_snapshot
WHERE department IS NOT NULL AND TRIM(department) <> ''
ON DUPLICATE KEY UPDATE department_name = VALUES(department_name);

INSERT INTO departments (department_name)
SELECT DISTINCT TRIM(department)
FROM hr_staging.stg_projects
WHERE department IS NOT NULL AND TRIM(department) <> ''
ON DUPLICATE KEY UPDATE department_name = VALUES(department_name);


-- Populate job roles.
INSERT INTO job_roles (job_title)
SELECT DISTINCT TRIM(job_role)
FROM hr_staging.stg_employee_snapshot
WHERE job_role IS NOT NULL AND TRIM(job_role) <> ''
ON DUPLICATE KEY UPDATE job_title = VALUES(job_title);


-- Populate current employees from the snapshot.
INSERT INTO employees (
    employee_number, employee_name, email, age, gender, marital_status,
    education, education_field, department_id, job_role_id, job_level,
    hire_date, attrition, business_travel, daily_rate, distance_from_home,
    environment_satisfaction, hourly_rate, job_involvement, job_satisfaction,
    monthly_income, monthly_rate, num_companies_worked, overtime,
    percent_salary_hike, performance_rating, relationship_satisfaction,
    stock_option_level, total_working_years, training_times_last_year,
    work_life_balance, years_at_company, years_in_current_role,
    years_since_last_promotion, years_with_curr_manager, employment_status
)
SELECT
    s.employee_number,
    COALESCE(s.synthetic_employee_name, CONCAT('Employee ', s.employee_number)),
    COALESCE(s.synthetic_employee_email, CONCAT('employee', s.employee_number, '@example.invalid')),
    s.age, s.gender, s.marital_status, s.education, s.education_field,
    d.department_id, j.job_role_id, s.job_level, s.synthetic_hire_date,
    s.attrition, s.business_travel, s.daily_rate, s.distance_from_home,
    s.environment_satisfaction, s.hourly_rate, s.job_involvement,
    s.job_satisfaction, s.monthly_income, s.monthly_rate,
    s.num_companies_worked, s.overtime, s.percent_salary_hike,
    s.performance_rating, s.relationship_satisfaction, s.stock_option_level,
    s.total_working_years, s.training_times_last_year, s.work_life_balance,
    s.years_at_company, s.years_in_current_role, s.years_since_last_promotion,
    s.years_with_curr_manager,
    CASE WHEN UPPER(COALESCE(s.attrition, 'NO')) = 'YES'
         THEN 'Terminated' ELSE 'Active' END
FROM hr_staging.stg_employee_snapshot s
JOIN departments d ON d.department_name = TRIM(s.department)
JOIN job_roles j ON j.job_title = TRIM(s.job_role)
ON DUPLICATE KEY UPDATE
    employee_name = VALUES(employee_name),
    email = VALUES(email),
    department_id = VALUES(department_id),
    job_role_id = VALUES(job_role_id),
    monthly_income = VALUES(monthly_income),
    employment_status = VALUES(employment_status),
    updated_at = CURRENT_TIMESTAMP;


-- Populate projects.
INSERT INTO projects (
    project_id, project_name, department_id, start_date, end_date,
    project_status, budget
)
SELECT
    p.project_id, p.project_name, d.department_id, p.start_date, p.end_date,
    p.status, p.budget
FROM hr_staging.stg_projects p
JOIN departments d ON d.department_name = TRIM(p.department)
ON DUPLICATE KEY UPDATE
    project_name = VALUES(project_name),
    department_id = VALUES(department_id),
    start_date = VALUES(start_date),
    end_date = VALUES(end_date),
    project_status = VALUES(project_status),
    budget = VALUES(budget);


-- Populate assignments using EmployeeNumber -> employee_id mapping.
INSERT INTO assignments (
    assignment_id, employee_id, project_id, is_primary, assigned_date,
    allocation_pct
)
SELECT
    a.assignment_id, e.employee_id, a.project_id, a.is_primary,
    a.assigned_date, a.allocation_pct
FROM hr_staging.stg_project_assignments a
JOIN employees e ON e.employee_number = a.employee_number
JOIN projects p ON p.project_id = a.project_id
ON DUPLICATE KEY UPDATE
    is_primary = VALUES(is_primary),
    assigned_date = VALUES(assigned_date),
    allocation_pct = VALUES(allocation_pct);


-- Populate performance reviews.
INSERT INTO performance_reviews (
    review_id, employee_id, project_id, review_date, review_year,
    performance_rating, job_satisfaction, review_score
)
SELECT
    r.review_id, e.employee_id, r.project_id, r.review_date, r.review_year,
    r.performance_rating, r.job_satisfaction, r.review_score
FROM hr_staging.stg_performance_reviews r
JOIN employees e ON e.employee_number = r.employee_number
JOIN projects p ON p.project_id = r.project_id
ON DUPLICATE KEY UPDATE
    review_date = VALUES(review_date),
    review_year = VALUES(review_year),
    performance_rating = VALUES(performance_rating),
    job_satisfaction = VALUES(job_satisfaction),
    review_score = VALUES(review_score);


-- =============================================================================
-- SECTION 4: OLAP STAR SCHEMA
--
-- Fact_PerformanceReviews grain:
--   One row per source ReviewID (one performance review event).
--
-- Dimensions:
--   Dim_Employee   : SCD Type 2; one row per employee version.
--   Dim_Department : one row per department.
--   Dim_Project    : one row per project, with department_name as a descriptive attribute.
--   Dim_Date       : one row per calendar date.
-- Pure star-schema rule: dimensions do not have foreign keys to other dimensions.
-- All four dimensions connect directly to Fact_PerformanceReviews.
--
-- Surrogate keys are generated in every dimension.
-- =============================================================================

USE hr_dw;

CREATE TABLE IF NOT EXISTS dim_department (
    department_sk    INT AUTO_INCREMENT PRIMARY KEY,
    department_name  VARCHAR(100) NOT NULL,
    source_department_id INT NULL,
    UNIQUE KEY uq_dim_department_name (department_name)
) ENGINE=InnoDB;


CREATE TABLE IF NOT EXISTS dim_project (
    project_sk       BIGINT AUTO_INCREMENT PRIMARY KEY,
    project_id       INT NOT NULL,
    project_name     VARCHAR(150) NOT NULL,
    department_name  VARCHAR(100),
    start_date       DATE,
    end_date         DATE,
    project_status   VARCHAR(30),
    budget           DECIMAL(15,2),
    UNIQUE KEY uq_dim_project_source (project_id),
    CONSTRAINT chk_project_dates
       CHECK (
    end_date IS NULL
    OR start_date IS NULL
    OR end_date >= start_date
     ),
   CONSTRAINT chk_project_budget
   CHECK (budget IS NULL OR budget >= 0)
) ENGINE=InnoDB;


CREATE TABLE IF NOT EXISTS dim_date (
    date_sk       INT PRIMARY KEY,
    full_date     DATE NOT NULL,
    day_number    TINYINT UNSIGNED NOT NULL,
    month_number  TINYINT UNSIGNED NOT NULL,
    month_name    VARCHAR(15) NOT NULL,
    quarter_number TINYINT UNSIGNED NOT NULL,
    year_number   SMALLINT NOT NULL,
    weekday_name VARCHAR(15) NOT NULL,
    UNIQUE KEY uq_dim_date_full_date (full_date),
    INDEX idx_dim_date_year_month (year_number, month_number)
) ENGINE=InnoDB;


CREATE TABLE IF NOT EXISTS dim_employee (
    employee_sk                BIGINT AUTO_INCREMENT PRIMARY KEY,
    employee_number            INT NOT NULL,
    employee_name              VARCHAR(150),
    employee_email             VARCHAR(255),
    age                         TINYINT UNSIGNED,
    attrition                   VARCHAR(5),
    business_travel             VARCHAR(30),
    daily_rate                  SMALLINT UNSIGNED,
    department_name             VARCHAR(100) NOT NULL,
    distance_from_home          TINYINT UNSIGNED,
    education                   TINYINT UNSIGNED,
    education_field             VARCHAR(100),
    gender                      VARCHAR(20),
    hourly_rate                 TINYINT UNSIGNED,
    job_involvement             TINYINT UNSIGNED,
    job_level                   TINYINT UNSIGNED,
    job_role                    VARCHAR(100),
    job_satisfaction            TINYINT UNSIGNED,
    marital_status              VARCHAR(30),
    monthly_income              DECIMAL(12,2),
    monthly_rate                INT UNSIGNED,
    num_companies_worked        TINYINT UNSIGNED,
    overtime                    VARCHAR(5),
    percent_salary_hike         TINYINT UNSIGNED,
    performance_rating          TINYINT UNSIGNED,
    relationship_satisfaction   TINYINT UNSIGNED,
    stock_option_level          TINYINT UNSIGNED,
    total_working_years         TINYINT UNSIGNED,
    training_times_last_year    TINYINT UNSIGNED,
    work_life_balance           TINYINT UNSIGNED,
    years_at_company            TINYINT UNSIGNED,
    years_in_current_role       TINYINT UNSIGNED,
    years_since_last_promotion  TINYINT UNSIGNED,
    years_with_curr_manager     TINYINT UNSIGNED,
    synthetic_hire_date         DATE,
    start_date                  DATE NOT NULL,
    end_date                    DATE NOT NULL,
    is_current                  BOOLEAN NOT NULL,
    change_reason               VARCHAR(100),
    INDEX idx_dim_employee_business_key (employee_number),
    INDEX idx_dim_employee_asof (employee_number, start_date, end_date),
    INDEX idx_dim_employee_current (employee_number, is_current),
    CONSTRAINT chk_dim_employee_dates
        CHECK (end_date >= start_date),
	CONSTRAINT uq_employee_version
         UNIQUE (employee_number, start_date)
) ENGINE=InnoDB;


CREATE TABLE IF NOT EXISTS fact_performance_reviews (
    fact_review_sk       BIGINT AUTO_INCREMENT PRIMARY KEY,
    source_review_id     INT NOT NULL,
    employee_sk          BIGINT NOT NULL,
    project_sk           BIGINT NOT NULL,
    department_sk        INT NOT NULL,
    review_date_sk       INT NOT NULL,
    performance_rating   TINYINT UNSIGNED,
    job_satisfaction     TINYINT UNSIGNED,
    review_score         DECIMAL(5,2),
    review_count         TINYINT UNSIGNED NOT NULL DEFAULT 1,
    UNIQUE KEY uq_fact_source_review (source_review_id),
    INDEX idx_fact_employee (employee_sk),
    INDEX idx_fact_project (project_sk),
    INDEX idx_fact_department (department_sk),
    INDEX idx_fact_date (review_date_sk),
    CONSTRAINT fk_fact_employee
        FOREIGN KEY (employee_sk) REFERENCES dim_employee(employee_sk),
    CONSTRAINT fk_fact_project
        FOREIGN KEY (project_sk) REFERENCES dim_project(project_sk),
    CONSTRAINT fk_fact_department
        FOREIGN KEY (department_sk) REFERENCES dim_department(department_sk),
    CONSTRAINT fk_fact_date
        FOREIGN KEY (review_date_sk) REFERENCES dim_date(date_sk),
    CONSTRAINT chk_fact_review_score
        CHECK (review_score IS NULL OR (review_score >= 0 AND review_score <= 100))
) ENGINE=InnoDB;

-- =============================================================================
-- EXISTING DATABASE MIGRATION NOTE (IMPORTANT)
-- =============================================================================
-- The CREATE TABLE IF NOT EXISTS statements above do NOT alter tables that
-- already exist. If hr_dw was created using the previous snowflake-style
-- version of this file, back up hr_dw and run the following one-time migration
-- BEFORE running Section 4A. Do NOT run this migration on a fresh database.
--
-- ALTER TABLE hr_dw.dim_project ADD COLUMN department_name VARCHAR(100) NULL;
-- UPDATE hr_dw.dim_project dp
-- JOIN hr_dw.dim_department dd ON dd.department_sk = dp.department_sk
-- SET dp.department_name = dd.department_name;
-- ALTER TABLE hr_dw.dim_project MODIFY department_name VARCHAR(100) NULL;
-- ALTER TABLE hr_dw.dim_project DROP FOREIGN KEY fk_dim_project_department;
-- ALTER TABLE hr_dw.dim_project DROP INDEX idx_dim_project_department;
-- ALTER TABLE hr_dw.dim_project DROP COLUMN department_sk;
--
-- ALTER TABLE hr_dw.dim_employee ADD COLUMN department_name VARCHAR(100) NULL
-- AFTER daily_rate;
-- UPDATE hr_dw.dim_employee de
-- JOIN hr_dw.dim_department dd ON dd.department_sk = de.department_sk
-- SET de.department_name = dd.department_name;
-- ALTER TABLE hr_dw.dim_employee MODIFY department_name VARCHAR(100) NOT NULL;
-- ALTER TABLE hr_dw.dim_employee DROP FOREIGN KEY fk_dim_employee_department;
-- ALTER TABLE hr_dw.dim_employee DROP COLUMN department_sk;
--
-- Verify department_name has no NULL values before making it NOT NULL. If the
-- old constraint/index names differ, inspect SHOW CREATE TABLE first.
-- The migration is deliberately commented out so a clean installation does
-- not try to alter columns that do not exist.
-- =============================================================================


-- =============================================================================
-- SECTION 4A: ETL STORED PROCEDURE - OLTP / STAGING TO DATA WAREHOUSE
--
-- This procedure performs the warehouse ETL in dependency order:
--   1. Load Dim_Department
--   2. Load Dim_Project
--   3. Load historical SCD Type 2 rows into Dim_Employee
--   4. Load Dim_Date
--   5. Load Fact_Performance_Reviews
--
-- CTEs (WITH clauses) clean, standardize, validate, and map source rows
-- before inserting them into warehouse tables.
--
-- It is designed to be rerunnable:
--   * Dimension rows are matched by their business/unique keys.
--   * Employee history rows are matched by employee_number + start_date.
--   * Fact rows are matched by source_review_id.
--
-- The transaction makes the warehouse refresh atomic. If any statement
-- fails, all changes made by this procedure are rolled back.
--
-- IMPORTANT:
--   * Import CSVs and populate staging/OLTP before calling this procedure.
--   * Validate SCD2 history (one current row per employee, no overlapping
--     effective dates) before running the ETL.
--   * This loads the SCD2 history already present in staging. It does not
--     generate new SCD2 versions when an employee is changed in the OLTP app.
-- =============================================================================

USE hr_dw;

DELIMITER $$

DROP PROCEDURE IF EXISTS sp_load_employee_analytics_dw$$

CREATE PROCEDURE sp_load_employee_analytics_dw()
BEGIN
    DECLARE v_invalid_scd2_rows BIGINT DEFAULT 0;

    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    -- Preflight SCD2 validation using ROW_NUMBER().
    -- The most recent version (highest start_date) must be the only
    -- current version for each employee. Abort the ETL rather than loading
    -- an inconsistent employee history.
    WITH ranked_history_check AS (
        SELECT
            employee_number,
            is_current,
            ROW_NUMBER() OVER (
                PARTITION BY employee_number
                ORDER BY start_date DESC, end_date DESC
            ) AS version_rank
        FROM hr_staging.stg_employee_scd2_history
        WHERE employee_number IS NOT NULL
    )
    SELECT COUNT(*)
      INTO v_invalid_scd2_rows
    FROM ranked_history_check
    WHERE (version_rank = 1 AND is_current <> 1)
       OR (version_rank > 1 AND is_current <> 0);

    IF v_invalid_scd2_rows > 0 THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT =
                'ETL stopped: staging employee history has invalid SCD2 current flags.';
    END IF;

    START TRANSACTION;

    -- STEP 1: Load department dimension.
    INSERT INTO dim_department (department_name)
    WITH cleaned_departments AS (
        SELECT DISTINCT TRIM(department_name) AS department_name
        FROM hr_oltp.departments
        WHERE department_name IS NOT NULL
          AND TRIM(department_name) <> ''
    )
    SELECT department_name
    FROM cleaned_departments
    ON DUPLICATE KEY UPDATE
        department_name = VALUES(department_name);

    -- STEP 2: Load project dimension.
    INSERT INTO dim_project (
        project_id, project_name, department_name, start_date, end_date,
        project_status, budget
    )
    WITH cleaned_projects AS (
        SELECT
            p.project_id,
            TRIM(p.project_name) AS project_name,
            TRIM(od.department_name) AS department_name,
            p.start_date,
            p.end_date,
            TRIM(p.project_status) AS project_status,
            p.budget
        FROM hr_oltp.projects p
        JOIN hr_oltp.departments od
          ON od.department_id = p.department_id
        WHERE p.project_name IS NOT NULL
          AND TRIM(p.project_name) <> ''
          AND od.department_name IS NOT NULL
          AND TRIM(od.department_name) <> ''
          AND (p.end_date IS NULL OR p.end_date >= p.start_date)
          AND (p.budget IS NULL OR p.budget >= 0)
    )
    SELECT
        project_id, project_name, department_name, start_date, end_date,
        project_status, budget
    FROM cleaned_projects
    ON DUPLICATE KEY UPDATE
        project_name = VALUES(project_name),
        department_name = VALUES(department_name),
        start_date = VALUES(start_date),
        end_date = VALUES(end_date),
        project_status = VALUES(project_status),
        budget = VALUES(budget);

    -- STEP 3: Load employee SCD Type 2 history from staging.
    -- A version is identified by employee_number + start_date.
    INSERT INTO dim_employee (
        employee_number, employee_name, employee_email, age, attrition,
        business_travel, daily_rate, department_name, distance_from_home,
        education, education_field, gender, hourly_rate, job_involvement,
        job_level, job_role, job_satisfaction, marital_status, monthly_income,
        monthly_rate, num_companies_worked, overtime, percent_salary_hike,
        performance_rating, relationship_satisfaction, stock_option_level,
        total_working_years, training_times_last_year, work_life_balance,
        years_at_company, years_in_current_role, years_since_last_promotion,
        years_with_curr_manager, synthetic_hire_date, start_date, end_date,
        is_current, change_reason
    )
    WITH cleaned_employee_history AS (
        SELECT
            h.*,
            NULLIF(TRIM(h.synthetic_employee_name), '') AS clean_employee_name,
            NULLIF(TRIM(h.synthetic_employee_email), '') AS clean_employee_email,
            NULLIF(TRIM(h.department), '') AS clean_department
        FROM hr_staging.stg_employee_scd2_history h
        WHERE h.employee_number IS NOT NULL
          AND h.start_date <= h.end_date
          AND h.is_current IN (0, 1)
    ),
    ranked_employee_history AS (
        SELECT
            h.*,
            ROW_NUMBER() OVER (
                PARTITION BY h.employee_number
                ORDER BY h.start_date DESC, h.end_date DESC
            ) AS version_rank
        FROM cleaned_employee_history h
    )
    SELECT
        h.employee_number,
        COALESCE(h.clean_employee_name, CONCAT('Employee ', h.employee_number)),
        h.clean_employee_email,
        h.age,
        h.attrition,
        h.business_travel,
        h.daily_rate,
        h.clean_department,
        h.distance_from_home,
        h.education,
        h.education_field,
        h.gender,
        h.hourly_rate,
        h.job_involvement,
        h.job_level,
        h.job_role,
        h.job_satisfaction,
        h.marital_status,
        h.monthly_income,
        h.monthly_rate,
        h.num_companies_worked,
        h.overtime,
        h.percent_salary_hike,
        h.performance_rating,
        h.relationship_satisfaction,
        h.stock_option_level,
        h.total_working_years,
        h.training_times_last_year,
        h.work_life_balance,
        h.years_at_company,
        h.years_in_current_role,
        h.years_since_last_promotion,
        h.years_with_curr_manager,
        h.synthetic_hire_date,
        h.start_date,
        h.end_date,
        h.is_current,
        h.change_reason
    FROM ranked_employee_history h
    WHERE h.clean_department IS NOT NULL
      AND NOT EXISTS (
          SELECT 1
          FROM dim_employee existing
          WHERE existing.employee_number = h.employee_number
            AND existing.start_date = h.start_date
      )
    ORDER BY h.employee_number, h.version_rank;

    -- STEP 4: Load date dimension from OLTP review dates.
    INSERT INTO dim_date (
        date_sk, full_date, day_number, month_number, month_name,
        quarter_number, year_number, weekday_name
    )
    WITH distinct_review_dates AS (
        SELECT DISTINCT review_date
        FROM hr_oltp.performance_reviews
        WHERE review_date IS NOT NULL
    )
    SELECT
        CAST(DATE_FORMAT(review_date, '%Y%m%d') AS UNSIGNED),
        review_date,
        DAY(review_date),
        MONTH(review_date),
        MONTHNAME(review_date),
        QUARTER(review_date),
        YEAR(review_date),
        DAYNAME(review_date)
    FROM distinct_review_dates
    ON DUPLICATE KEY UPDATE
        full_date = VALUES(full_date);

    -- STEP 5: Load the fact table.
    -- Resolve the employee's historical dimension version valid on review_date.
    INSERT INTO fact_performance_reviews (
        source_review_id, employee_sk, project_sk, department_sk,
        review_date_sk, performance_rating, job_satisfaction, review_score,
        review_count
    )
    WITH resolved_review_source AS (
        SELECT
            r.review_id,
            r.review_date,
            r.performance_rating,
            r.job_satisfaction,
            r.review_score,
            oe.employee_number,
            r.project_id
        FROM hr_oltp.performance_reviews r
        JOIN hr_oltp.employees oe
          ON oe.employee_id = r.employee_id
        WHERE r.review_date IS NOT NULL
    ),
    mapped_reviews AS (
        SELECT
            r.review_id,
            de.employee_sk,
            dp.project_sk,
            dd.department_sk,
            CAST(DATE_FORMAT(r.review_date, '%Y%m%d') AS UNSIGNED) AS review_date_sk,
            r.performance_rating,
            r.job_satisfaction,
            r.review_score
        FROM resolved_review_source r
        JOIN dim_employee de
          ON de.employee_number = r.employee_number
         AND r.review_date >= de.start_date
         AND r.review_date <= de.end_date
        JOIN dim_project dp
          ON dp.project_id = r.project_id
        JOIN dim_department dd
          ON dd.department_name = de.department_name
    )
    SELECT
        review_id,
        employee_sk,
        project_sk,
        department_sk,
        review_date_sk,
        performance_rating,
        job_satisfaction,
        review_score,
        1
    FROM mapped_reviews
    ON DUPLICATE KEY UPDATE
        employee_sk = VALUES(employee_sk),
        project_sk = VALUES(project_sk),
        department_sk = VALUES(department_sk),
        review_date_sk = VALUES(review_date_sk),
        performance_rating = VALUES(performance_rating),
        job_satisfaction = VALUES(job_satisfaction),
        review_score = VALUES(review_score),
        review_count = VALUES(review_count);

    COMMIT;

    -- Return a compact ETL completion summary.
    SELECT 'dim_department' AS table_name, COUNT(*) AS warehouse_rows
    FROM dim_department
    UNION ALL
    SELECT 'dim_project', COUNT(*) FROM dim_project
    UNION ALL
    SELECT 'dim_employee', COUNT(*) FROM dim_employee
    UNION ALL
    SELECT 'dim_date', COUNT(*) FROM dim_date
    UNION ALL
    SELECT 'fact_performance_reviews', COUNT(*) FROM fact_performance_reviews;
END$$

DELIMITER ;

-- Execute the warehouse ETL after staging and OLTP loads are complete.
CALL sp_load_employee_analytics_dw();


-- =============================================================================
-- SECTION 4B: AUTOMATIC SCD TYPE 2 CHANGE CAPTURE FROM OLTP EMPLOYEES
--
-- Call this procedure after an employee is inserted/updated in hr_oltp.
-- It compares the current OLTP employee snapshot with the current
-- Dim_Employee version. If tracked attributes changed:
--   1. Expire the old dimension version (end_date = effective_date - 1 day).
--   2. Insert a new current version with a new employee_sk.
--
-- New OLTP employees are inserted as their first dimension version.
-- Unchanged employees are not inserted again.
--
-- p_effective_date is supplied by the caller so the business-effective date
-- is explicit and repeatable. It must be later than the current version's
-- start_date for any changed employee.
--
-- This procedure tracks the attributes represented in Dim_Employee.
-- OLTP-only fields such as manager_id and employment_status are not tracked
-- because corresponding columns do not exist in the current Dim_Employee.
--
-- NOTE: The first historical load should be completed before using this
-- procedure for ongoing changes. Do not call it concurrently with the main
-- warehouse ETL procedure.
-- =============================================================================

USE hr_dw;

DELIMITER $$

DROP PROCEDURE IF EXISTS sp_apply_employee_scd2_changes$$

CREATE PROCEDURE sp_apply_employee_scd2_changes(
    IN p_effective_date DATE
)
BEGIN
    DECLARE v_changed_count INT DEFAULT 0;

    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        DROP TEMPORARY TABLE IF EXISTS tmp_employee_scd2_snapshot;
        RESIGNAL;
    END;

    IF p_effective_date IS NULL THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Effective date cannot be NULL.';
    END IF;

    START TRANSACTION;

    DROP TEMPORARY TABLE IF EXISTS tmp_employee_scd2_snapshot;

    -- Define the temporary snapshot explicitly with a primary key.
    -- Aiven has sql_require_primary_key enabled, so CREATE TABLE ... AS
    -- SELECT without a primary key is rejected.
    CREATE TEMPORARY TABLE tmp_employee_scd2_snapshot (
        employee_number INT NOT NULL PRIMARY KEY,
        employee_name VARCHAR(150),
        employee_email VARCHAR(255),
        age TINYINT UNSIGNED,
        attrition VARCHAR(5),
        business_travel VARCHAR(30),
        daily_rate SMALLINT UNSIGNED,
        department_name VARCHAR(100),
        distance_from_home TINYINT UNSIGNED,
        education TINYINT UNSIGNED,
        education_field VARCHAR(100),
        gender VARCHAR(20),
        hourly_rate TINYINT UNSIGNED,
        job_involvement TINYINT UNSIGNED,
        job_level TINYINT UNSIGNED,
        job_role VARCHAR(100),
        job_satisfaction TINYINT UNSIGNED,
        marital_status VARCHAR(30),
        monthly_income DECIMAL(12,2),
        monthly_rate INT UNSIGNED,
        num_companies_worked TINYINT UNSIGNED,
        overtime VARCHAR(5),
        percent_salary_hike TINYINT UNSIGNED,
        performance_rating TINYINT UNSIGNED,
        relationship_satisfaction TINYINT UNSIGNED,
        stock_option_level TINYINT UNSIGNED,
        total_working_years TINYINT UNSIGNED,
        training_times_last_year TINYINT UNSIGNED,
        work_life_balance TINYINT UNSIGNED,
        years_at_company TINYINT UNSIGNED,
        years_in_current_role TINYINT UNSIGNED,
        years_since_last_promotion TINYINT UNSIGNED,
        years_with_curr_manager TINYINT UNSIGNED,
        synthetic_hire_date DATE,
        attribute_hash CHAR(64)
    ) ENGINE=InnoDB;

    INSERT INTO tmp_employee_scd2_snapshot (
        employee_number, employee_name, employee_email, age, attrition,
        business_travel, daily_rate, department_name, distance_from_home,
        education, education_field, gender, hourly_rate, job_involvement,
        job_level, job_role, job_satisfaction, marital_status, monthly_income,
        monthly_rate, num_companies_worked, overtime, percent_salary_hike,
        performance_rating, relationship_satisfaction, stock_option_level,
        total_working_years, training_times_last_year, work_life_balance,
        years_at_company, years_in_current_role, years_since_last_promotion,
        years_with_curr_manager, synthetic_hire_date, attribute_hash
    )
    SELECT
        e.employee_number,
        e.employee_name,
        e.email,
        e.age,
        e.attrition,
        e.business_travel,
        e.daily_rate,
        d.department_name,
        e.distance_from_home,
        e.education,
        e.education_field,
        e.gender,
        e.hourly_rate,
        e.job_involvement,
        e.job_level,
        j.job_title,
        e.job_satisfaction,
        e.marital_status,
        e.monthly_income,
        e.monthly_rate,
        e.num_companies_worked,
        e.overtime,
        e.percent_salary_hike,
        e.performance_rating,
        e.relationship_satisfaction,
        e.stock_option_level,
        e.total_working_years,
        e.training_times_last_year,
        e.work_life_balance,
        e.years_at_company,
        e.years_in_current_role,
        e.years_since_last_promotion,
        e.years_with_curr_manager,
        e.hire_date,
        SHA2(
            CAST(JSON_ARRAY(
                e.employee_name, e.email, e.age, e.attrition,
                e.business_travel, e.daily_rate, d.department_name,
                e.distance_from_home, e.education, e.education_field,
                e.gender, e.hourly_rate, e.job_involvement, e.job_level,
                j.job_title, e.job_satisfaction, e.marital_status,
                e.monthly_income, e.monthly_rate, e.num_companies_worked,
                e.overtime, e.percent_salary_hike, e.performance_rating,
                e.relationship_satisfaction, e.stock_option_level,
                e.total_working_years, e.training_times_last_year,
                e.work_life_balance, e.years_at_company,
                e.years_in_current_role, e.years_since_last_promotion,
                e.years_with_curr_manager, e.hire_date
            ) AS CHAR),
            256
        )
    FROM hr_oltp.employees e
    JOIN hr_oltp.departments d
      ON d.department_id = e.department_id
    JOIN hr_oltp.job_roles j
      ON j.job_role_id = e.job_role_id;

    -- Reject a backdated or same-day change that would create an invalid
    -- zero-length/overlapping SCD2 interval.
    SELECT COUNT(*)
      INTO v_changed_count
    FROM tmp_employee_scd2_snapshot s
    JOIN dim_employee de
      ON de.employee_number = s.employee_number
     AND de.is_current = TRUE
    WHERE de.start_date >= p_effective_date
      AND de.employee_name IS NOT NULL
      AND SHA2(
            CAST(JSON_ARRAY(
                de.employee_name, de.employee_email, de.age, de.attrition,
                de.business_travel, de.daily_rate, de.department_name,
                de.distance_from_home, de.education, de.education_field,
                de.gender, de.hourly_rate, de.job_involvement, de.job_level,
                de.job_role, de.job_satisfaction, de.marital_status,
                de.monthly_income, de.monthly_rate, de.num_companies_worked,
                de.overtime, de.percent_salary_hike, de.performance_rating,
                de.relationship_satisfaction, de.stock_option_level,
                de.total_working_years, de.training_times_last_year,
                de.work_life_balance, de.years_at_company,
                de.years_in_current_role, de.years_since_last_promotion,
                de.years_with_curr_manager, de.synthetic_hire_date
            ) AS CHAR),
            256
          ) <> s.attribute_hash;

    IF v_changed_count > 0 THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Effective date must be later than the current SCD2 start_date for changed employees.';
    END IF;

    -- Expire only current versions whose tracked attributes have changed.
    UPDATE dim_employee de
    JOIN tmp_employee_scd2_snapshot s
      ON s.employee_number = de.employee_number
    SET
        de.end_date = DATE_SUB(p_effective_date, INTERVAL 1 DAY),
        de.is_current = FALSE,
        de.change_reason = 'Tracked employee attribute changed'
    WHERE de.is_current = TRUE
      AND SHA2(
            CAST(JSON_ARRAY(
                de.employee_name, de.employee_email, de.age, de.attrition,
                de.business_travel, de.daily_rate, de.department_name,
                de.distance_from_home, de.education, de.education_field,
                de.gender, de.hourly_rate, de.job_involvement, de.job_level,
                de.job_role, de.job_satisfaction, de.marital_status,
                de.monthly_income, de.monthly_rate, de.num_companies_worked,
                de.overtime, de.percent_salary_hike, de.performance_rating,
                de.relationship_satisfaction, de.stock_option_level,
                de.total_working_years, de.training_times_last_year,
                de.work_life_balance, de.years_at_company,
                de.years_in_current_role, de.years_since_last_promotion,
                de.years_with_curr_manager, de.synthetic_hire_date
            ) AS CHAR),
            256
          ) <> s.attribute_hash;

    -- Insert a new version for changed employees and first versions for
    -- employees that do not yet exist in Dim_Employee.
    INSERT INTO dim_employee (
        employee_number, employee_name, employee_email, age, attrition,
        business_travel, daily_rate, department_name, distance_from_home,
        education, education_field, gender, hourly_rate, job_involvement,
        job_level, job_role, job_satisfaction, marital_status, monthly_income,
        monthly_rate, num_companies_worked, overtime, percent_salary_hike,
        performance_rating, relationship_satisfaction, stock_option_level,
        total_working_years, training_times_last_year, work_life_balance,
        years_at_company, years_in_current_role, years_since_last_promotion,
        years_with_curr_manager, synthetic_hire_date, start_date, end_date,
        is_current, change_reason
    )
    SELECT
        s.employee_number,
        s.employee_name,
        s.employee_email,
        s.age,
        s.attrition,
        s.business_travel,
        s.daily_rate,
        s.department_name,
        s.distance_from_home,
        s.education,
        s.education_field,
        s.gender,
        s.hourly_rate,
        s.job_involvement,
        s.job_level,
        s.job_role,
        s.job_satisfaction,
        s.marital_status,
        s.monthly_income,
        s.monthly_rate,
        s.num_companies_worked,
        s.overtime,
        s.percent_salary_hike,
        s.performance_rating,
        s.relationship_satisfaction,
        s.stock_option_level,
        s.total_working_years,
        s.training_times_last_year,
        s.work_life_balance,
        s.years_at_company,
        s.years_in_current_role,
        s.years_since_last_promotion,
        s.years_with_curr_manager,
        s.synthetic_hire_date,
        p_effective_date,
        '2099-12-31',
        TRUE,
        CASE
            WHEN EXISTS (
                SELECT 1
                FROM dim_employee old_de
                WHERE old_de.employee_number = s.employee_number
                  AND old_de.is_current = FALSE
                  AND old_de.end_date = DATE_SUB(p_effective_date, INTERVAL 1 DAY)
            )
            THEN 'Tracked employee attribute changed'
            ELSE 'Initial OLTP employee load'
        END
    FROM tmp_employee_scd2_snapshot s
    LEFT JOIN dim_employee current_de
      ON current_de.employee_number = s.employee_number
     AND current_de.is_current = TRUE
    WHERE current_de.employee_sk IS NULL;

    DROP TEMPORARY TABLE IF EXISTS tmp_employee_scd2_snapshot;

    COMMIT;

    SELECT
        'SCD Type 2 synchronization completed' AS status,
        p_effective_date AS effective_date,
        (SELECT COUNT(*)
         FROM dim_employee
         WHERE is_current = TRUE) AS current_employee_versions;
END$$

DELIMITER ;

-- Example usage (run manually AFTER updating an employee in hr_oltp):
-- CALL hr_dw.sp_apply_employee_scd2_changes(CURDATE());
--
-- Verify an employee's history (replace 1001 with a real employee_number):
-- SELECT employee_number, employee_name, department_name, monthly_income,
--        start_date, end_date, is_current, change_reason
-- FROM hr_dw.dim_employee
-- WHERE employee_number = 1001
-- ORDER BY start_date;


-- =============================================================================
-- SECTION 5: VALIDATION QUERIES
-- Run these after loading each layer to verify row counts and relationships.
-- =============================================================================

-- Staging row counts.
SELECT 'stg_employee_snapshot' AS table_name, COUNT(*) AS row_count
FROM hr_staging.stg_employee_snapshot
UNION ALL
SELECT 'stg_employee_scd2_history', COUNT(*)
FROM hr_staging.stg_employee_scd2_history
UNION ALL
SELECT 'stg_performance_reviews', COUNT(*)
FROM hr_staging.stg_performance_reviews
UNION ALL
SELECT 'stg_project_assignments', COUNT(*)
FROM hr_staging.stg_project_assignments
UNION ALL
SELECT 'stg_projects', COUNT(*)
FROM hr_staging.stg_projects;


-- OLTP row counts.
SELECT 'departments' AS table_name, COUNT(*) AS row_count FROM hr_oltp.departments
UNION ALL SELECT 'job_roles', COUNT(*) FROM hr_oltp.job_roles
UNION ALL SELECT 'employees', COUNT(*) FROM hr_oltp.employees
UNION ALL SELECT 'projects', COUNT(*) FROM hr_oltp.projects
UNION ALL SELECT 'assignments', COUNT(*) FROM hr_oltp.assignments
UNION ALL SELECT 'performance_reviews', COUNT(*) FROM hr_oltp.performance_reviews;


-- Warehouse row counts.
SELECT 'dim_department' AS table_name, COUNT(*) AS row_count FROM hr_dw.dim_department
UNION ALL SELECT 'dim_project', COUNT(*) FROM hr_dw.dim_project
UNION ALL SELECT 'dim_employee', COUNT(*) FROM hr_dw.dim_employee
UNION ALL SELECT 'dim_date', COUNT(*) FROM hr_dw.dim_date
UNION ALL SELECT 'fact_performance_reviews', COUNT(*) FROM hr_dw.fact_performance_reviews;


-- Star-schema structural check: dimensions should not contain FKs to dimensions.
-- The expected dimension FKs exist only on fact_performance_reviews.
SELECT TABLE_NAME, CONSTRAINT_NAME, REFERENCED_TABLE_NAME
FROM information_schema.KEY_COLUMN_USAGE
WHERE TABLE_SCHEMA = 'hr_dw'
  AND REFERENCED_TABLE_NAME IS NOT NULL
ORDER BY TABLE_NAME, CONSTRAINT_NAME;


-- Check that each employee has exactly one current SCD2 version.
SELECT employee_number, SUM(is_current = TRUE) AS current_versions
FROM hr_dw.dim_employee
GROUP BY employee_number
HAVING SUM(is_current = TRUE) <> 1;


-- Check for missing employee references in staging reviews.
SELECT COUNT(*) AS reviews_with_unknown_employee
FROM hr_staging.stg_performance_reviews r
LEFT JOIN hr_oltp.employees e
    ON e.employee_number = r.employee_number
WHERE e.employee_id IS NULL;


-- Check for missing project references in staging assignments.
SELECT COUNT(*) AS assignments_with_unknown_project
FROM hr_staging.stg_project_assignments a
LEFT JOIN hr_oltp.projects p ON p.project_id = a.project_id
WHERE p.project_id IS NULL;


-- Check total allocation per employee (interpret with care if assignments
-- are not all concurrent; the CSV does not provide an assignment end date).
SELECT e.employee_number, SUM(a.allocation_pct) AS total_allocation_pct
FROM hr_oltp.assignments a
JOIN hr_oltp.employees e ON e.employee_id = a.employee_id
GROUP BY e.employee_number
HAVING SUM(a.allocation_pct) > 100;


/*
Enterprise Employee Analytics & Data Warehouse System
Advanced SQL: CTEs, Window Functions, Stored Procedures

Updated OLAP schema:
  dim_employee, dim_project, dim_date, dim_department
  fact_performance_reviews (the only fact table)

Fact grain: one row per performance review.
department_sk in the fact represents the employee's department at review time.
dim_employee is SCD Type 2; employee_sk identifies a specific historical version.
*/

USE hr_dw;

-- 1. Department-wise performance summary
SELECT d.department_name, COUNT(*) AS total_reviews,
       ROUND(AVG(f.review_score), 2) AS average_review_score,
       ROUND(AVG(f.performance_rating), 2) AS average_performance_rating
FROM fact_performance_reviews f
JOIN dim_department d ON f.department_sk = d.department_sk
GROUP BY d.department_sk, d.department_name
ORDER BY average_review_score DESC;

-- 2. Year-wise review volume and average performance
SELECT dt.year_number, COUNT(*) AS total_reviews,
       ROUND(AVG(f.review_score), 2) AS average_review_score
FROM fact_performance_reviews f
JOIN dim_date dt ON f.review_date_sk = dt.date_sk
GROUP BY dt.year_number
ORDER BY dt.year_number;

-- 3. Project-wise performance summary
SELECT p.project_id, p.project_name, COUNT(*) AS total_reviews,
       ROUND(AVG(f.review_score), 2) AS average_review_score,
       MAX(f.review_score) AS highest_score, MIN(f.review_score) AS lowest_score
FROM fact_performance_reviews f
JOIN dim_project p ON f.project_sk = p.project_sk
GROUP BY p.project_id, p.project_name
ORDER BY average_review_score DESC;

-- 4. Performance-rating distribution
SELECT performance_rating, COUNT(*) AS total_reviews,
       ROUND(100.0 * COUNT(*) /
             NULLIF((SELECT COUNT(*) FROM fact_performance_reviews), 0), 2) AS percentage
FROM fact_performance_reviews
GROUP BY performance_rating
ORDER BY performance_rating;

-- 5. Department-wise job satisfaction
SELECT d.department_name, COUNT(*) AS total_reviews,
       ROUND(AVG(f.job_satisfaction), 2) AS average_job_satisfaction
FROM fact_performance_reviews f
JOIN dim_department d ON f.department_sk = d.department_sk
GROUP BY d.department_sk, d.department_name
ORDER BY average_job_satisfaction DESC;

-- 6. Monthly performance trend
SELECT dt.year_number, dt.month_number, dt.month_name,
       COUNT(*) AS total_reviews, ROUND(AVG(f.review_score), 2) AS average_score
FROM fact_performance_reviews f
JOIN dim_date dt ON f.review_date_sk = dt.date_sk
GROUP BY dt.year_number, dt.month_number, dt.month_name
ORDER BY dt.year_number, dt.month_number;

-- 7. Employees whose average score is above the company average (CTE)
WITH employee_performance AS (
    SELECT e.employee_number, e.employee_name, f.department_sk,
           COUNT(*) AS review_count, AVG(f.review_score) AS employee_average
    FROM fact_performance_reviews f
    JOIN dim_employee e ON f.employee_sk = e.employee_sk
    GROUP BY e.employee_number, e.employee_name, f.department_sk
),
company_average AS (
    SELECT AVG(review_score) AS overall_average
    FROM fact_performance_reviews
)
SELECT ep.employee_number, ep.employee_name, d.department_name,
       ep.review_count, ROUND(ep.employee_average, 2) AS employee_average,
       ROUND(ca.overall_average, 2) AS company_average
FROM employee_performance ep
JOIN dim_department d ON ep.department_sk = d.department_sk
CROSS JOIN company_average ca
WHERE ep.employee_average > ca.overall_average
ORDER BY ep.employee_average DESC;

-- 8. Departments performing above the company average (CTE)
WITH department_performance AS (
    SELECT department_sk, COUNT(*) AS total_reviews, AVG(review_score) AS department_average
    FROM fact_performance_reviews
    GROUP BY department_sk
),
company_performance AS (
    SELECT AVG(review_score) AS company_average FROM fact_performance_reviews
)
SELECT d.department_name, dp.total_reviews,
       ROUND(dp.department_average, 2) AS department_average,
       ROUND(cp.company_average, 2) AS company_average
FROM department_performance dp
JOIN dim_department d ON dp.department_sk = d.department_sk
CROSS JOIN company_performance cp
WHERE dp.department_average > cp.company_average
ORDER BY dp.department_average DESC;

-- 9. Year-over-year performance change using LAG() (CTE + window function)
WITH yearly_performance AS (
    SELECT dt.year_number, COUNT(*) AS total_reviews, AVG(f.review_score) AS average_score
    FROM fact_performance_reviews f
    JOIN dim_date dt ON f.review_date_sk = dt.date_sk
    GROUP BY dt.year_number
),
yearly_comparison AS (
    SELECT year_number, total_reviews, average_score,
           LAG(average_score) OVER (ORDER BY year_number) AS previous_year_average
    FROM yearly_performance
)
SELECT year_number, total_reviews,
       ROUND(average_score, 2) AS average_score,
       ROUND(previous_year_average, 2) AS previous_year_average,
       ROUND(average_score - previous_year_average, 2) AS score_change,
       ROUND(100.0 * (average_score - previous_year_average) /
             NULLIF(previous_year_average, 0), 2) AS percentage_change
FROM yearly_comparison
ORDER BY year_number;

-- 10. Reviews above their department's average score (CTE)
WITH department_average AS (
    SELECT department_sk, AVG(review_score) AS average_score
    FROM fact_performance_reviews
    GROUP BY department_sk
)
SELECT e.employee_number, e.employee_name, d.department_name,
       f.review_score, ROUND(da.average_score, 2) AS department_average
FROM fact_performance_reviews f
JOIN dim_employee e ON f.employee_sk = e.employee_sk
JOIN dim_department d ON f.department_sk = d.department_sk
JOIN department_average da ON f.department_sk = da.department_sk
WHERE f.review_score > da.average_score
ORDER BY d.department_name, f.review_score DESC;

-- 11. Top-performing employees in each department using DENSE_RANK()
-- Rank employee-level averages, not individual review rows.
WITH employee_department_performance AS (
    SELECT e.employee_number, e.employee_name, f.department_sk,
           COUNT(*) AS review_count, AVG(f.review_score) AS average_score
    FROM fact_performance_reviews f
    JOIN dim_employee e ON f.employee_sk = e.employee_sk
    GROUP BY e.employee_number, e.employee_name, f.department_sk
),
ranked_employees AS (
    SELECT employee_number, employee_name, department_sk, review_count, average_score,
           DENSE_RANK() OVER (
               PARTITION BY department_sk ORDER BY average_score DESC
           ) AS department_rank
    FROM employee_department_performance
)
SELECT r.employee_number, r.employee_name, d.department_name, r.review_count,
       ROUND(r.average_score, 2) AS average_score, r.department_rank
FROM ranked_employees r
JOIN dim_department d ON r.department_sk = d.department_sk
WHERE r.department_rank <= 5
ORDER BY d.department_name, r.department_rank, r.employee_name;

-- 12. Latest review for each employee using ROW_NUMBER()
WITH employee_reviews AS (
    SELECT e.employee_number, e.employee_name, f.source_review_id,
           dt.full_date AS review_date, f.review_score,
           ROW_NUMBER() OVER (
               PARTITION BY e.employee_number
               ORDER BY dt.full_date DESC, f.source_review_id DESC
           ) AS row_num
    FROM fact_performance_reviews f
    JOIN dim_employee e ON f.employee_sk = e.employee_sk
    JOIN dim_date dt ON f.review_date_sk = dt.date_sk
)
SELECT employee_number, employee_name, source_review_id, review_date, review_score
FROM employee_reviews
WHERE row_num = 1
ORDER BY employee_number;

-- 13. Compare each employee's review with their previous review using LAG()
WITH review_sequence AS (
    SELECT e.employee_number, e.employee_name, dt.full_date AS review_date,
           f.review_score,
           LAG(f.review_score) OVER (
               PARTITION BY e.employee_number
               ORDER BY dt.full_date, f.source_review_id
           ) AS previous_review_score
    FROM fact_performance_reviews f
    JOIN dim_employee e ON f.employee_sk = e.employee_sk
    JOIN dim_date dt ON f.review_date_sk = dt.date_sk
)
SELECT employee_number, employee_name, review_date, review_score,
       previous_review_score, review_score - previous_review_score AS score_difference
FROM review_sequence
ORDER BY employee_number, review_date;

-- 14. Show the next review score using LEAD()
SELECT e.employee_number, e.employee_name, dt.full_date AS review_date,
       f.review_score,
       LEAD(f.review_score) OVER (
           PARTITION BY e.employee_number
           ORDER BY dt.full_date, f.source_review_id
       ) AS next_review_score
FROM fact_performance_reviews f
JOIN dim_employee e ON f.employee_sk = e.employee_sk
JOIN dim_date dt ON f.review_date_sk = dt.date_sk
ORDER BY e.employee_number, dt.full_date;

-- 15. Cumulative number of reviews by department over time
WITH daily_department_reviews AS (
    SELECT f.department_sk, dt.full_date, COUNT(*) AS daily_reviews
    FROM fact_performance_reviews f
    JOIN dim_date dt ON f.review_date_sk = dt.date_sk
    GROUP BY f.department_sk, dt.full_date
)
SELECT d.department_name, x.full_date, x.daily_reviews,
       SUM(x.daily_reviews) OVER (
           PARTITION BY x.department_sk
           ORDER BY x.full_date
           ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
       ) AS cumulative_reviews
FROM daily_department_reviews x
JOIN dim_department d ON x.department_sk = d.department_sk
ORDER BY d.department_name, x.full_date;

-- 16. Compare each review score with the overall average using AVG() OVER()
SELECT e.employee_number, e.employee_name, f.review_score,
       ROUND(AVG(f.review_score) OVER (), 2) AS overall_average,
       ROUND(f.review_score - AVG(f.review_score) OVER (), 2) AS difference_from_average
FROM fact_performance_reviews f
JOIN dim_employee e ON f.employee_sk = e.employee_sk;

-- 17. Current attrition count and percentage by department
-- is_current prevents historical SCD2 versions from being double-counted.
SELECT e.department_name, COUNT(*) AS current_employee_count,
       SUM(CASE WHEN LOWER(e.attrition) = 'yes' THEN 1 ELSE 0 END) AS attrition_count,
       ROUND(100.0 * SUM(CASE WHEN LOWER(e.attrition) = 'yes' THEN 1 ELSE 0 END) /
             NULLIF(COUNT(*), 0), 2) AS attrition_percentage
FROM dim_employee e
WHERE e.is_current = TRUE
GROUP BY e.department_name
ORDER BY attrition_percentage DESC;

-- 18. Current attrition by job role
SELECT e.job_role, COUNT(*) AS employee_count,
       SUM(CASE WHEN LOWER(e.attrition) = 'yes' THEN 1 ELSE 0 END) AS attrition_count,
       ROUND(100.0 * SUM(CASE WHEN LOWER(e.attrition) = 'yes' THEN 1 ELSE 0 END) /
             NULLIF(COUNT(*), 0), 2) AS attrition_percentage
FROM dim_employee e
WHERE e.is_current = TRUE
GROUP BY e.job_role
ORDER BY attrition_percentage DESC;

-- 19. Current attrition by overtime
SELECT e.overtime, COUNT(*) AS employee_count,
       SUM(CASE WHEN LOWER(e.attrition) = 'yes' THEN 1 ELSE 0 END) AS attrition_count,
       ROUND(100.0 * SUM(CASE WHEN LOWER(e.attrition) = 'yes' THEN 1 ELSE 0 END) /
             NULLIF(COUNT(*), 0), 2) AS attrition_percentage
FROM dim_employee e
WHERE e.is_current = TRUE
GROUP BY e.overtime
ORDER BY attrition_percentage DESC;

-- 20. Current attrition by job satisfaction
SELECT e.job_satisfaction, COUNT(*) AS employee_count,
       SUM(CASE WHEN LOWER(e.attrition) = 'yes' THEN 1 ELSE 0 END) AS attrition_count,
       ROUND(100.0 * SUM(CASE WHEN LOWER(e.attrition) = 'yes' THEN 1 ELSE 0 END) /
             NULLIF(COUNT(*), 0), 2) AS attrition_percentage
FROM dim_employee e
WHERE e.is_current = TRUE
GROUP BY e.job_satisfaction
ORDER BY e.job_satisfaction;

-- 21. Inspect all SCD2 versions of one employee (replace sample employee number)
SELECT employee_number, employee_name, department_name, job_role, job_level,
       monthly_income, start_date, end_date, is_current, change_reason
FROM dim_employee
WHERE employee_number = 1001
ORDER BY start_date;

-- 22. Find employees with more than one current SCD2 version (expected: no rows)
SELECT employee_number, COUNT(*) AS current_version_count
FROM dim_employee
WHERE is_current = TRUE
GROUP BY employee_number
HAVING COUNT(*) > 1;

-- 23. Check current flag and end-date consistency (sentinel: 2099-12-31)
SELECT employee_number, start_date, end_date, is_current
FROM dim_employee
WHERE (is_current = TRUE AND end_date <> '2099-12-31')
   OR (is_current = FALSE AND end_date = '2099-12-31');

-- 24. Find overlapping SCD2 effective date ranges (expected: no rows)
SELECT a.employee_number,
       a.employee_sk AS version_1, b.employee_sk AS version_2,
       a.start_date AS version_1_start, a.end_date AS version_1_end,
       b.start_date AS version_2_start, b.end_date AS version_2_end
FROM dim_employee a
JOIN dim_employee b
  ON a.employee_number = b.employee_number
 AND a.employee_sk < b.employee_sk
 AND a.start_date <= b.end_date
 AND b.start_date <= a.end_date;

-- 25. Create a reusable review-level employee performance view
CREATE OR REPLACE VIEW vw_employee_performance AS
SELECT e.employee_number, e.employee_name, d.department_name,
       p.project_name, dt.full_date AS review_date,
       f.performance_rating, f.job_satisfaction, f.review_score
FROM fact_performance_reviews f
JOIN dim_employee e ON f.employee_sk = e.employee_sk
JOIN dim_department d ON f.department_sk = d.department_sk
JOIN dim_project p ON f.project_sk = p.project_sk
JOIN dim_date dt ON f.review_date_sk = dt.date_sk;

-- 26. Read the view
SELECT *
FROM vw_employee_performance
ORDER BY review_date DESC
LIMIT 20;

-- 27-29. Stored procedures
-- Run this section in MySQL Workbench with delimiter handling enabled.
DELIMITER //

DROP PROCEDURE IF EXISTS GetDepartmentPerformance//
CREATE PROCEDURE GetDepartmentPerformance(IN p_department_sk INT)
BEGIN
    SELECT d.department_name, COUNT(*) AS total_reviews,
           ROUND(AVG(f.review_score), 2) AS average_score,
           MAX(f.review_score) AS highest_score,
           MIN(f.review_score) AS lowest_score
    FROM dim_department d
    JOIN fact_performance_reviews f ON d.department_sk = f.department_sk
    WHERE d.department_sk = p_department_sk
    GROUP BY d.department_sk, d.department_name;
END//

DROP PROCEDURE IF EXISTS GetTotalReviews//
CREATE PROCEDURE GetTotalReviews(OUT p_total_reviews BIGINT)
BEGIN
    SELECT COUNT(*) INTO p_total_reviews
    FROM fact_performance_reviews;
END//

DROP PROCEDURE IF EXISTS GetYearlyPerformance//
CREATE PROCEDURE GetYearlyPerformance(IN p_year INT)
BEGIN
    SELECT dt.year_number, COUNT(*) AS total_reviews,
           ROUND(AVG(f.review_score), 2) AS average_score
    FROM fact_performance_reviews f
    JOIN dim_date dt ON f.review_date_sk = dt.date_sk
    WHERE dt.year_number = p_year
    GROUP BY dt.year_number;
END//
DELIMITER ;

-- 30. Call stored procedures (use values that exist in your warehouse)
CALL GetDepartmentPerformance(1);
CALL GetTotalReviews(@total_reviews);
SELECT @total_reviews AS total_reviews;
CALL GetYearlyPerformance(2026);

-- 31. Inspect indexes
SHOW INDEX FROM fact_performance_reviews;

-- 32. Explain department filtering
EXPLAIN
SELECT employee_sk, department_sk, review_score
FROM fact_performance_reviews
WHERE department_sk = 1;

-- 33. Analyze department aggregation (executes the query)
EXPLAIN ANALYZE
SELECT department_sk, AVG(review_score)
FROM fact_performance_reviews
GROUP BY department_sk;

-- 34. Check review-score range (expected: no rows)
SELECT *
FROM fact_performance_reviews
WHERE review_score < 0 OR review_score > 100;

-- 35. Compare fact row count with distinct source review count
SELECT COUNT(*) AS total_fact_rows,
       COUNT(DISTINCT source_review_id) AS distinct_source_reviews
FROM fact_performance_reviews;

-- 36. Current employees without a performance review
SELECT e.employee_number, e.employee_name, e.department_name
FROM dim_employee e
WHERE e.is_current = TRUE
  AND NOT EXISTS (
      SELECT 1
      FROM fact_performance_reviews f
      WHERE f.employee_sk = e.employee_sk
  )
ORDER BY e.employee_number;





-- =============================================================================
-- END OF MASTER SQL FILE
-- =============================================================================
