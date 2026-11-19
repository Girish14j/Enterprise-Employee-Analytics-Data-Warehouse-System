

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


