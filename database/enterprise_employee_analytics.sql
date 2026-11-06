
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
    PRIMARY KEY (employee_number, start_date),
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
    s.age,
    s.gender,
    s.marital_status,
    s.education,
    s.education_field,
    d.department_id,
    j.job_role_id,
    s.job_level,
    s.synthetic_hire_date,
    s.attrition,
    s.business_travel,
    s.daily_rate,
    s.distance_from_home,
    s.environment_satisfaction,
    s.hourly_rate,
    s.job_involvement,
    s.job_satisfaction,
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
    CASE
        WHEN UPPER(COALESCE(s.attrition, 'NO')) = 'YES'
        THEN 'Terminated'
        ELSE 'Active'
    END
FROM hr_staging.stg_employee_snapshot s
JOIN departments d
    ON d.department_name COLLATE utf8mb4_unicode_ci
       = TRIM(s.department) COLLATE utf8mb4_unicode_ci
JOIN job_roles j
    ON j.job_title COLLATE utf8mb4_unicode_ci
       = TRIM(s.job_role) COLLATE utf8mb4_unicode_ci
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
    p.project_id,
    p.project_name,
    d.department_id,
    p.start_date,
    p.end_date,
    p.status,
    p.budget
FROM hr_staging.stg_projects p
JOIN departments d
    ON d.department_name COLLATE utf8mb4_unicode_ci
       = TRIM(p.department) COLLATE utf8mb4_unicode_ci
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
--   Dim_Project    : one row per project.
--   Dim_Date       : one row per calendar date.
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
    department_sk    INT NOT NULL,
    start_date       DATE,
    end_date         DATE,
    project_status   VARCHAR(30),
    budget           DECIMAL(15,2),
    UNIQUE KEY uq_dim_project_source (project_id),
    INDEX idx_dim_project_department (department_sk),
    CONSTRAINT fk_dim_project_department
        FOREIGN KEY (department_sk) REFERENCES dim_department(department_sk)
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
    department_sk               INT NOT NULL,
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
    CONSTRAINT fk_dim_employee_department
        FOREIGN KEY (department_sk) REFERENCES dim_department(department_sk),
    CONSTRAINT chk_dim_employee_dates
        CHECK (end_date >= start_date)
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
-- SECTION 4A: LOAD WAREHOUSE DIMENSIONS FROM OLTP / SCD2 STAGING
--
-- Execute after Section 3A has populated OLTP and after CSVs are imported.
-- The SCD2 history source is loaded into Dim_Employee with its original
-- start_date, end_date, is_current and change_reason values.
--
-- The department dimension is loaded first because employee/project dimensions
-- reference it. Project dimension follows. Date dimension is populated from
-- review dates. The fact load uses the employee version valid on ReviewDate.
--
-- Validate that each employee has exactly one current SCD2 row and that
-- historical intervals do not overlap before executing.
-- =============================================================================

-- Load department dimension.
INSERT INTO dim_department (department_name)
SELECT DISTINCT department_name
FROM hr_oltp.departments
ON DUPLICATE KEY UPDATE department_name = VALUES(department_name);


-- Load project dimension.
INSERT INTO dim_project (
    project_id, project_name, department_sk, start_date, end_date,
    project_status, budget
)
SELECT
    p.project_id, p.project_name, dd.department_sk, p.start_date, p.end_date,
    p.project_status, p.budget
FROM hr_oltp.projects p
JOIN hr_oltp.departments od ON od.department_id = p.department_id
JOIN dim_department dd ON dd.department_name = od.department_name
ON DUPLICATE KEY UPDATE
    project_name = VALUES(project_name),
    department_sk = VALUES(department_sk),
    start_date = VALUES(start_date),
    end_date = VALUES(end_date),
    project_status = VALUES(project_status),
    budget = VALUES(budget);


-- Load employee SCD2 versions from history staging.
-- This is an initial historical load. Do not truncate Dim_Employee in routine
-- refreshes. The NOT EXISTS check prevents duplicate versions with the same
-- employee key and validity start date.
INSERT INTO dim_employee (
    employee_number, employee_name, employee_email, age, attrition,
    business_travel, daily_rate, department_sk, distance_from_home,
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
    h.employee_number, h.synthetic_employee_name, h.synthetic_employee_email,
    h.age, h.attrition, h.business_travel, h.daily_rate, dd.department_sk,
    h.distance_from_home, h.education, h.education_field, h.gender,
    h.hourly_rate, h.job_involvement, h.job_level, h.job_role,
    h.job_satisfaction, h.marital_status, h.monthly_income, h.monthly_rate,
    h.num_companies_worked, h.overtime, h.percent_salary_hike,
    h.performance_rating, h.relationship_satisfaction, h.stock_option_level,
    h.total_working_years, h.training_times_last_year, h.work_life_balance,
    h.years_at_company, h.years_in_current_role, h.years_since_last_promotion,
    h.years_with_curr_manager, h.synthetic_hire_date, h.start_date, h.end_date,
    h.is_current, h.change_reason
FROM hr_staging.stg_employee_scd2_history h
JOIN dim_department dd ON dd.department_name = TRIM(h.department)
WHERE NOT EXISTS (
    SELECT 1
    FROM dim_employee existing
    WHERE existing.employee_number = h.employee_number
      AND existing.start_date = h.start_date
);


-- Populate date dimension from the distinct review dates.
INSERT INTO dim_date (
    date_sk, full_date, day_number, month_number, month_name,
    quarter_number, year_number, weekday_name
)
SELECT DISTINCT
    CAST(DATE_FORMAT(r.review_date, '%Y%m%d') AS UNSIGNED),
    r.review_date,
    DAY(r.review_date),
    MONTH(r.review_date),
    MONTHNAME(r.review_date),
    QUARTER(r.review_date),
    YEAR(r.review_date),
    DAYNAME(r.review_date)
FROM hr_oltp.performance_reviews r
ON DUPLICATE KEY UPDATE full_date = VALUES(full_date);


-- Load performance review facts.
-- Employee dimension row is selected using the review date's SCD2 validity.
INSERT INTO fact_performance_reviews (
    source_review_id, employee_sk, project_sk, department_sk,
    review_date_sk, performance_rating, job_satisfaction, review_score,
    review_count
)
SELECT
    r.review_id,
    de.employee_sk,
    dp.project_sk,
    de.department_sk,
    CAST(DATE_FORMAT(r.review_date, '%Y%m%d') AS UNSIGNED),
    r.performance_rating,
    r.job_satisfaction,
    r.review_score,
    1
FROM hr_oltp.performance_reviews r
JOIN hr_oltp.employees oe ON oe.employee_id = r.employee_id
JOIN dim_employee de
  ON de.employee_number = oe.employee_number
 AND r.review_date >= de.start_date
 AND r.review_date <= de.end_date
JOIN dim_project dp ON dp.project_id = r.project_id
ON DUPLICATE KEY UPDATE
    employee_sk = VALUES(employee_sk),
    project_sk = VALUES(project_sk),
    department_sk = VALUES(department_sk),
    review_date_sk = VALUES(review_date_sk),
    performance_rating = VALUES(performance_rating),
    job_satisfaction = VALUES(job_satisfaction),
    review_score = VALUES(review_score);


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


-- =============================================================================
-- END OF MASTER SQL FILE
-- =============================================================================
