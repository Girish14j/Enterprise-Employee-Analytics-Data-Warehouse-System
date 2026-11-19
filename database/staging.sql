

CREATE DATABASE IF NOT EXISTS hr_staging
    CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE DATABASE IF NOT EXISTS hr_oltp
    CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE DATABASE IF NOT EXISTS hr_dw
    CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;



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


