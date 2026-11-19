-- Apply to existing deployments before starting the login-enabled app.
USE hr_oltp;

CREATE TABLE IF NOT EXISTS user_accounts (
    account_id    BIGINT AUTO_INCREMENT PRIMARY KEY,
    employee_id   BIGINT NOT NULL,
    username      VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                             ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_user_accounts_employee (employee_id),
    UNIQUE KEY uq_user_accounts_username (username),
    CONSTRAINT fk_user_accounts_employee
        FOREIGN KEY (employee_id) REFERENCES employees(employee_id)
        ON DELETE CASCADE
) ENGINE=InnoDB;
