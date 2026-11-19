# Enterprise Employee Analytics & Data Warehouse System

A cloud-ready HR analytics platform. It replaces legacy, disconnected HR systems with a staging area, a
normalized operational database and a star-schema data warehouse, connected by a Python ETL pipeline and
an object-oriented backend. HR and executive teams use a Streamlit web app to onboard employees, manage
projects and reviews, track historical changes with **SCD Type 2**, and explore analytical dashboards.

**Live app:** <add the Streamlit Community Cloud URL once deployed>
**Full documentation (Google Doc):** <add link>

> All data in this project is synthetic. It is generated from the public IBM HR Analytics dataset and does
> not describe real people.

## Table of contents

1. [Features](#features)
2. [Tech stack](#tech-stack)
3. [Architecture](#architecture)
4. [Repository structure](#repository-structure)
5. [Getting started](#getting-started)
6. [Data synthesis and staging](#data-synthesis-and-staging)
7. [Data models](#data-models)
8. [SCD Type 2 and point-in-time facts](#scd-type-2-and-point-in-time-facts)
9. [SQL scripts](#sql-scripts)
10. [ETL pipeline](#etl-pipeline)
11. [Object-oriented backend](#object-oriented-backend)
12. [Streamlit application](#streamlit-application)
13. [Testing and data quality](#testing-and-data-quality)
14. [Deployment](#deployment)
15. [Version control workflow](#version-control-workflow)
16. [Requirements coverage](#requirements-coverage)
17. [Troubleshooting](#troubleshooting)
18. [Design decisions, assumptions and limitations](#design-decisions-assumptions-and-limitations)

## Features

- **100,000+ synthetic employees** scaled from the 1,470-row IBM dataset, with engineered employee history,
  projects, assignments and reviews.
- **Three-database design** on one MySQL 8 service: `hr_staging` (landing), `hr_oltp` (normalized
  operational data) and `hr_dw` (star schema).
- **SCD Type 2** employee dimension that records department, job role, level and salary changes without
  ever overwriting history.
- **Point-in-time facts:** every review is linked to the employee version that was valid on the review date.
- **Set-based, idempotent ETL** that runs in a single transaction and can sync one record or everything.
- **Object-oriented backend:** Singleton database connection, validating entity classes, a data access
  layer and a service layer.
- **Streamlit app** with data-entry forms that trigger the warehouse update, and four analytical dashboards.

## Tech stack

| Area | Technology |
| --- | --- |
| Language | Python 3.10+ (object-oriented) |
| Databases | MySQL 8.0+ (hosted on Aiven, SSL-verified; MySQL Workbench for design and ad hoc SQL) |
| Data access | SQLAlchemy with mysql-connector-python and PyMySQL |
| Data synthesis | pandas, NumPy, Faker |
| Front end | Streamlit (1.50+) with Plotly charts |
| Testing | pytest |
| Version control | Git and GitHub (feature branches, Pull Requests) |
| Deployment | Streamlit Community Cloud |

## Architecture

### Three-database layout

| Database | Role | Contents |
| --- | --- | --- |
| `hr_staging` | Landing area | Raw synthesizer output: `stg_employee_snapshot`, `stg_employee_scd2_history`, `stg_projects`, `stg_project_assignments`, `stg_performance_reviews` |
| `hr_oltp` | Operational (OLTP) | Normalized tables: `departments`, `job_roles`, `employees`, `projects`, `assignments`, `performance_reviews` |
| `hr_dw` | Warehouse (OLAP) | Star schema: `dim_department`, `dim_project`, `dim_date`, `dim_employee` (SCD Type 2), `fact_performance_reviews` |

All three databases live on the same MySQL service, so queries use fully qualified names such as
`hr_oltp.employees`. That lets the ETL read OLTP and write the warehouse inside one transaction.

### Data flow

```
IBM HR CSV (1,470 rows)
   │  data_synthesizer.py (pandas + Faker)
   ▼
5 synthetic CSVs (100,000+ employees, SCD2 history, projects, assignments, reviews)
   │  scripts/import_staging_csvs.py
   ▼
hr_staging  ──(SQL sections 3 / 3A)──►  hr_oltp  ──(ETLPipeline)──►  hr_dw  (star schema)
                                          ▲                              │
       Streamlit forms ─► Managers ───────┘                              ▼
                                               Streamlit dashboard ◄─ AnalyticsManager
```

**ER diagram (OLTP):** <add link to the editable Draw.io / Lucidchart file>
**Dimensional model (OLAP):** <add link to the editable Draw.io / Lucidchart file>

### What happens when a user changes something

1. A Streamlit form calls `HRService`.
2. `HRService` saves the change to `hr_oltp` through a manager class, in its own transaction.
3. `HRService` then runs the matching ETL step, which copies the change into `hr_dw`.
4. If a tracked attribute changed, the ETL closes the employee's current history row and opens a new one.
5. The dashboards read only from `hr_dw`.

If the ETL step fails after the OLTP save, the data stays saved. The user sees a warning and can retry from
the **Warehouse sync** page, so nothing is lost and nothing is half-written.

## Repository structure

```
.
├── data_generator/
│   └── data_synthesizer.py          # scales the IBM data to 100,000+ rows, engineers SCD2 history
├── scripts/
│   ├── import_staging_csvs.py       # validated, batched, retrying CSV import into hr_staging
│   └── run_oltp_to_olap.py          # bulk ETL runner: hr_oltp -> hr_dw with validation
├── database/
│   └── enterprise_employee_analytics.sql   # DDL, loads, validation, analytical queries, view, procedures
├── src/
│   ├── database/db_manager.py       # DatabaseConnection: Singleton owning one pooled engine
│   ├── exceptions.py                # exception hierarchy
│   ├── models/                      # Employee, Project, Review entities with validating fields
│   ├── managers/                    # EmployeeManager, ProjectManager, ReviewManager, AnalyticsManager
│   ├── etl/pipeline.py              # ETLPipeline and its loaders
│   └── services/hr_service.py       # HRService: save to OLTP, then sync the warehouse
├── streamlit_app.py                 # app entry point (Home page)
├── pages/                           # Streamlit pages
├── ui/common.py                     # shared UI helpers, cached lookups, chart styling
├── tests/                           # unit tests (no database needed)
├── .streamlit/                      # theme config and a secrets template
├── .env.example                     # template for local database settings
└── requirements.txt
```

Local-only files that are never committed (see `.gitignore`): `.env`, `certificates/`, `.venv/`,
`data/generated/`, `.streamlit/secrets.toml`.

## Getting started

**Requirements:** Python 3.10 or newer, a MySQL 8.0+ service (the project uses Aiven) and its CA certificate.

### 1. Install

```bash
git clone https://github.com/Girish14j/Enterprise-Employee-Analytics-Data-Warehouse-System.git
cd Enterprise-Employee-Analytics-Data-Warehouse-System
python -m venv .venv
# Windows (PowerShell):  .venv\Scripts\Activate.ps1
# macOS / Linux:         source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure the database

Copy `.env.example` to `.env` in the project root and fill it in:

```
MYSQL_HOST=your-aiven-hostname
MYSQL_PORT=your-aiven-port
MYSQL_USER=avnadmin
MYSQL_PASSWORD=your-aiven-password
MYSQL_CA_CERT=certificates/ca.pem
```

Put the Aiven CA certificate at `certificates/ca.pem`. The names `DB_HOST`, `DB_PORT`, `DB_USER`,
`DB_PASSWORD` and `DB_SSL_CA` are also accepted. `.env` and the certificate are git-ignored and must never
be committed.

### 3. Build and load the data

Skip this section if the shared database is already loaded.

1. Download the IBM HR Analytics Employee Attrition & Performance CSV (`WA_Fn-UseC_-HR-Employee-Attrition.csv`).
2. Generate the synthetic data (see [Data synthesis and staging](#data-synthesis-and-staging)).
3. In MySQL, run sections 1 and 2 of `database/enterprise_employee_analytics.sql` to create the databases and
   the staging tables.
4. Import the CSVs into staging: `python scripts/import_staging_csvs.py`
5. Run sections 3 and 3A to create and populate the OLTP tables.
6. Run sections 4 and 4A to create the star schema and load the dimensions and facts. As an alternative to the
   SQL load, run the ETL: `python scripts/run_oltp_to_olap.py`
7. Run the section 5 validation queries and confirm they return the expected results.

Run the scripts from the repository root. They resolve paths and imports relative to it, so if one is run from
the `scripts/` folder, copy it to the repository root first.

### 4. Run the tests and the app

```bash
python -m pytest tests -q
streamlit run streamlit_app.py
```

The app opens at http://localhost:8501, and the sidebar shows the database connection status.

## Data synthesis and staging

The base data is the IBM HR Analytics Employee Attrition & Performance dataset: about 1,470 rows describing a
single point in time. `data_generator/data_synthesizer.py` turns it into a large, repeatable dataset.

| Step | Behavior |
| --- | --- |
| Validate | Checks required columns exist and that `EmployeeNumber` is unique in the source |
| Scale | Samples source rows with replacement to reach `--target-rows` (default and minimum 100,000), then assigns new sequential employee numbers |
| Identity | Faker (`en_IN` locale) generates names; emails are `employee<N>@example.test`, so they are always unique |
| Hire dates | Derived from `YearsAtCompany` plus a random 0 to 364 days before the as-of date |
| Income noise | `MonthlyIncome` is multiplied by a random factor between 0.90 and 1.10 so duplicated rows are not identical |
| SCD2 history | One current row per employee, plus one earlier row for a subset (below) |
| Projects | 300 projects by default, spread across departments, budgets of 50,000 to 2,000,000, status Completed or Active |
| Assignments | Each employee gets one primary project in their department (50, 75 or 100 percent allocation); about 30 percent also get a secondary project (25 percent) |
| Reviews | Annual reviews dated 15 December for the last 3 years. Rating is the source rating with small noise, clipped to 1 to 4; `review_score` is rating × 20 plus normal noise, clipped to 0 to 100 |
| Validate and save | Checks SCD2 integrity, writes five CSV files to `data/generated`, and can optionally load MySQL |

### Engineered SCD Type 2 history

The IBM data has no history, so the synthesizer creates it. Employees with at least 3 years at the company
are eligible. By default 20 percent of them (`--historical-pct`) receive one earlier version, chosen as:

| Change type | Probability | What differs in the earlier version |
| --- | --- | --- |
| Promotion | 40% | Job level is one lower and income is roughly 10 to 25 percent lower (promotions at level 1 become salary bumps) |
| Transfer | 20% | A different department, with a job role that is valid for that department |
| Salary bump | 40% | Income is roughly 5 to 15 percent lower |

The change date falls at least one year after hire, within the last three years, and at least 180 days before
the as-of date. The earlier row runs from the hire date to the day before the change; the current row starts
on the change date and ends on `2099-12-31`. Before saving, `validate_history()` confirms that every employee
has exactly one current row, no `end_date` precedes its `start_date`, and version ranges do not overlap.

### Running the synthesizer

```bash
python data_generator/data_synthesizer.py \
  --input WA_Fn-UseC_-HR-Employee-Attrition.csv \
  --target-rows 100000 --historical-pct 0.20 \
  --num-projects 300 --review-years 3 \
  --as-of-date 2026-11-10 --seed 42 --output-dir data/generated
```

Fixing `--seed` and `--as-of-date` makes the output fully repeatable. Add `--load-mysql` to load the files
directly into `hr_staging` with pandas.

### Loading staging

`scripts/import_staging_csvs.py` is the robust import path for a cloud database. It maps CSV headers to
staging columns, validates columns and row counts, inserts in small batches, retries temporary connection
failures (up to 5 times) and verifies the row counts at the end.

## Data models

### OLTP design (`hr_oltp`)

The operational schema is normalized so repeated descriptive values live in one place.

| Table | Key | Purpose and notable constraints |
| --- | --- | --- |
| `departments` | `department_id` (auto) | Unique `department_name` |
| `job_roles` | `job_role_id` (auto) | Unique `job_title` |
| `employees` | `employee_id` (auto, BIGINT) | `employee_number` is the unique business key; unique email; foreign keys to department, job role and a self-referencing `manager_id`; `employment_status` is Active, Inactive or Terminated |
| `projects` | `project_id` | Foreign key to department; `end_date` must not precede `start_date`; budget must be non-negative |
| `assignments` | `assignment_id` | Links employees to projects; unique `(employee_id, project_id)`; `allocation_pct` greater than 0 and at most 100 |
| `performance_reviews` | `review_id` | Foreign keys to employee and project; `review_score` between 0 and 100 |

Salary history is represented by SCD Type 2 versions in the warehouse, so there is no separate salary-history
table in OLTP.

### OLAP design (`hr_dw`): star schema

**Grain of the fact table:** one row per performance review.

| Table | Surrogate key | Notes |
| --- | --- | --- |
| `dim_department` | `department_sk` | Unique `department_name`; keeps `source_department_id` |
| `dim_project` | `project_sk` | Business key `project_id`; stores `department_name` as a descriptive attribute |
| `dim_date` | `date_sk` (YYYYMMDD integer) | Day, month, month name, quarter, year and weekday name |
| `dim_employee` | `employee_sk` | SCD Type 2; business key `employee_number`; tracks department, role, level and income with `start_date`, `end_date`, `is_current` and `change_reason` |
| `fact_performance_reviews` | `fact_review_sk` | Foreign keys `employee_sk`, `project_sk`, `department_sk`, `review_date_sk`; measures `performance_rating`, `job_satisfaction`, `review_score`, `review_count` |

Key design rules:

- **Surrogate keys everywhere.** Every dimension has its own auto-generated key, independent of source keys.
- **Pure star schema.** Dimensions have no foreign keys to other dimensions. Department names are stored as
  attributes in `dim_employee` and `dim_project`, and only the fact table references all four dimensions.
- **Traceability.** `source_review_id` is unique on the fact table, which prevents duplicate loads and ties
  each fact back to OLTP.
- **Query performance.** Indexes cover each foreign key, `dim_employee (employee_number, start_date, end_date)`
  for as-of lookups, and `dim_employee (employee_number, is_current)` for current-state queries.

## SCD Type 2 and point-in-time facts

### Tracked attributes

`dim_employee` tracks **department, job role, job level and monthly income**. A change to any of them creates
a new version. All other attributes (name, email, attrition and similar) are refreshed in place (Type 1).

| Column | Meaning |
| --- | --- |
| `employee_sk` | Surrogate key, unique to each version |
| `employee_number` | Business key, shared by all versions of one person |
| `start_date` | First day this version is valid |
| `end_date` | Last day this version is valid; `2099-12-31` for the current version |
| `is_current` | 1 for the latest version, otherwise 0 |
| `change_reason` | Initial hire record, promotion, transfer or salary_bump from the synthetic data; New employee, Department change, Job role change, Job level change or Salary change from the live ETL |

Constraints: `end_date >= start_date`, and `(employee_number, start_date)` is unique.

### Worked example

Employee 42 moves from Sales to Research & Development on 2026-11-10.

| employee_sk | employee_number | department_name | start_date | end_date | is_current | change_reason |
| --- | --- | --- | --- | --- | --- | --- |
| 1042 | 42 | Sales | 2021-03-01 | **2026-11-09** | **0** | Initial hire record |
| 98211 | 42 | Research & Development | **2026-11-10** | 2099-12-31 | 1 | Department change |

The old row is closed (`end_date` becomes the day before the change, `is_current` becomes 0) and a new row is
inserted with a new surrogate key.

### ETL rules for SCD2

- **Same-day correction.** If the current version started on the change date, it is corrected in place.
  Closing it would create an invalid range where `end_date` is before `start_date`.
- **Close.** For every current row whose tracked attributes differ from OLTP, set `end_date` to the change
  date minus one day and `is_current` to 0.
- **Open.** For each employee left without a current row, insert a new version with a new surrogate key,
  `start_date` equal to the change date, `end_date` of `2099-12-31`, `is_current` of 1 and a descriptive
  `change_reason`. Untracked attributes are carried forward from the previous version.
- **New employees.** Employees with no version at all get a first row with the reason New employee.
- **Type 1 refresh.** Untracked attributes are updated in place on current rows.

Comparisons use null-safe equality (`<=>`), so a missing value is never mistaken for a change.

### Point-in-time fact loading

Each review is linked to the employee version that was valid **on the review date**:

```sql
JOIN hr_dw.dim_employee de
  ON de.employee_number = e.employee_number
 AND r.review_date BETWEEN de.start_date AND de.end_date
```

Old reviews therefore keep pointing at the old department, and `department_sk` on the fact row is resolved
from that version's department name. A CTE using `ROW_NUMBER() OVER (PARTITION BY review_id ORDER BY
start_date DESC)` guarantees exactly one version per review, even if date ranges ever overlapped.

## SQL scripts

`database/enterprise_employee_analytics.sql` is the master file for MySQL 8.0+.

| Section | Content |
| --- | --- |
| 1 to 2 | Create the three databases and the staging tables |
| 3 / 3A | Create the OLTP tables and load them from staging |
| 4 / 4A | Create the star schema and load dimensions and facts, including the initial SCD2 history load |
| 5 | Validation queries: row counts per layer, one current row per employee, missing references, allocation totals |
| Analytics | 36 numbered queries, one view and three stored procedures |

**Advanced SQL used**

| Technique | Examples |
| --- | --- |
| CTEs | Employees and departments above the company average; reviews above their department average |
| `DENSE_RANK()` | Top five employees per department, ranking employee-level averages |
| `ROW_NUMBER()` | Latest review per employee |
| `LAG()` / `LEAD()` | Year-over-year change; previous and next review scores |
| Window aggregates | Cumulative reviews by department over time; `AVG() OVER()` against the overall average |
| View | `vw_employee_performance`, a reusable review-level performance view |
| Stored procedures | `GetDepartmentPerformance(IN p_department_sk)`, `GetTotalReviews(OUT p_total_reviews)`, `GetYearlyPerformance(IN p_year)` |

In MySQL Workbench, run the procedure section with delimiter handling enabled (the script uses `DELIMITER //`).

## ETL pipeline

`src/etl/pipeline.py` implements the OLTP-to-warehouse movement as set-based SQL orchestrated by Python
classes. A common `BaseLoader` is extended by one loader per target, and `ETLPipeline` runs them in order.
Every step is idempotent, so running the pipeline twice changes nothing.

| Step | Source | Target | Type |
| --- | --- | --- | --- |
| 1 | `hr_oltp.departments` | `dim_department` | Type 1 |
| 2 | `hr_oltp.projects` | `dim_project` | Type 1 |
| 3 | `hr_oltp.performance_reviews` | `dim_date` (missing days only) | Insert |
| 4 | `hr_oltp.employees` | `dim_employee` | **SCD Type 2** |
| 5 | `hr_oltp.performance_reviews` | `fact_performance_reviews` | Insert |

**Safety and quality**

- No row-by-row Python, so the pipeline scales to 100,000+ rows. Tables are never dropped, truncated or replaced.
- One run is one transaction: everything is applied or nothing is. Lock-wait and deadlock errors are retried
  up to three times.
- Text comparisons across schemas use an explicit collation, which avoids MySQL error 1267 when `hr_oltp`
  and `hr_dw` use different collations.
- `validate_scd2()` checks rules the database cannot enforce: every employee has exactly one current row, no
  overlapping version ranges, no OLTP employees missing from the warehouse, no reviews missing from the fact
  table, no unknown department names, and no fact row whose department differs from its employee version.
  Every value should be `0`.
- `pending_changes()` previews what a full sync would do without writing anything.

**Entry points**

```python
etl = ETLPipeline()
etl.sync_employee(employee_number)   # after an employee is created or changed
etl.sync_review(review_id)           # after a review is submitted
etl.sync_project(project_id)         # after a project is created
etl.run_full_sync()                  # everything
```

For a bulk run, `scripts/run_oltp_to_olap.py` previews the pending changes, runs the full sync, prints a
per-step report, runs the validation checks and prints the final warehouse row counts.

## Object-oriented backend

| Concept | Implementation |
| --- | --- |
| **Singleton** | `DatabaseConnection` uses a thread-safe metaclass (`SingletonMeta`) so the whole app shares one SSL-verified, pooled SQLAlchemy engine (`pool_pre_ping`, connection recycling). It provides `fetch_all`, `fetch_one`, `fetch_df`, `execute`, `insert`, `transaction`, `call_procedure` and schema-inspection helpers. |
| **Inheritance** | `BaseManager` extends `DatabaseConnection`; `EmployeeManager`, `ProjectManager`, `ReviewManager` and `AnalyticsManager` extend `BaseManager`. ETL loaders also extend `DatabaseConnection`. Each is its own singleton, but all share one engine. |
| **Encapsulation** | `Employee`, `Project` and `Review` use validating field descriptors. Invalid values (type, range, email format, dates) raise `ValidationError` at assignment time. Behavior lives on the class, for example `Employee.promote()`, `Employee.give_raise()`, `Project.is_overdue()` and `Review.rating_label`. |
| **Data access layer** | Managers handle CRUD on `hr_oltp`; `AnalyticsManager` runs read-only queries on `hr_dw`. |
| **Error handling** | Every operation is wrapped in `try/except` and translated into project exceptions (`DatabaseError`, `ValidationError`, `DuplicateRecordError`, `ETLError`, and others). Writes run in transactions that roll back on any error, so the UI never handles raw driver errors. |
| **Service layer** | `HRService` saves to OLTP, then triggers the matching ETL step and returns an `ActionResult` describing both outcomes. |
| **Schema-aware inserts** | Managers read the live column list and skip columns a table does not have, logging a warning instead of failing. Tables whose key is not auto-increment (projects, assignments, reviews) get their next id inside the same transaction. |

## Streamlit application

| Page | What it does |
| --- | --- |
| **Home** | Warehouse KPIs (current employees, SCD2 history records, reviews, average score) and a data-flow explainer |
| **Onboard employee** | Creates an employee in OLTP and their first warehouse record. The employee number is assigned automatically (the next free number) and cannot be edited. |
| **Update employee** | Search with a preview table of matching employees. Changes department, job role, level, salary or status. A tracked change creates an SCD2 version and shows a version timeline. |
| **Projects** | Create projects, assign employees with an allocation percentage, list projects |
| **Reviews** | Submit a performance review; it becomes a fact row linked to the correct employee version |
| **Analytics dashboard** | Four tabs reading only from the warehouse (below) |
| **Warehouse sync** | Pending work, manual full sync, data-quality checks and any employee's version history |

### Dashboard tabs

| Tab | Content | SQL technique |
| --- | --- | --- |
| Year-over-year trends | Average score by year and by department, with change versus the previous year | CTE, `LAG()` |
| Top performers | Top N employees per department, with a minimum-reviews filter so one lucky review cannot win | CTE, `DENSE_RANK() OVER (PARTITION BY department ...)` |
| Attrition risk | Attrition rate by department and job role, plus a rule-based risk score for current employees who have not left | CTE, `ROW_NUMBER()`, `LAG()`, window `AVG()` |
| Project bottlenecks | Overdue projects, and open projects in the bottom quarter by average review score | CTE, `NTILE(4)` |

### Attrition risk score (0 to 100)

Calculated from each employee's latest review. Employees whose attrition flag is already Yes are excluded.
This is a transparent rule-based score, not a predictive model.

| Rule | Points |
| --- | --- |
| Job satisfaction of 2 or lower | 40 |
| Review score fell by 10 or more points | 20 |
| Score below the department average | 20 |
| Monthly income below 80% of the department average | 20 |

Bands: Low is up to 20, Medium is up to 40, High is above 40.

## Testing and data quality

- **Unit tests:** `tests/test_entities.py` covers entity validation (required fields, email normalization,
  ranges, future hire dates) and runs without a database: `python -m pytest tests -q`.
- **Generator validation:** `validate_history()` rejects missing or duplicate current rows, invalid date
  ranges and overlaps before any file is written.
- **Warehouse validation:** `ETLPipeline.validate_scd2()` and the SQL section 5 queries confirm current-row
  uniqueness, non-overlapping ranges and complete fact coverage. The **Warehouse sync** page runs the same
  checks from the app.
- **Row counts:** the import script and the ETL runner print counts per layer for reconciliation.

## Deployment

The app is deployed on **Streamlit Community Cloud** with `streamlit_app.py` as the main file.

1. Push the code to GitHub and create a new app from the repository, branch `main`.
2. In **Advanced settings → Secrets** (or later, **App settings → Secrets**), add the database settings. Use
   `.streamlit/secrets.toml.example` as a template:

   ```toml
   MYSQL_HOST = "your-aiven-hostname"
   MYSQL_PORT = "your-aiven-port"
   MYSQL_USER = "avnadmin"
   MYSQL_PASSWORD = "your-aiven-password"
   DB_SSL_CA_PEM = """-----BEGIN CERTIFICATE-----
   ...paste the full certificate text...
   -----END CERTIFICATE-----"""
   ```

3. Streamlit Cloud has no local certificate file, so the certificate text goes in `DB_SSL_CA_PEM` instead of
   a file path.
4. In the Aiven service settings, allow connections from Streamlit Cloud.

The app copies values from `st.secrets` into environment variables at start-up, so the same code runs locally
and in the cloud. Free Community Cloud apps go to sleep when idle, so open the app and wake it before a demo.

## Version control workflow

Work is done on feature branches (for example `feature/database-design`, `feature/data-synthesizer`,
`feature/etl-pipeline`, `feature/streamlit-dashboard`) and merged into `main` through Pull Requests, never by
pushing to `main` directly. Secrets, `.env` files and certificates are excluded with `.gitignore`.

## Requirements coverage

| Requirement | Where it is implemented |
| --- | --- |
| Scale the IBM dataset to 100,000+ rows with pandas and Faker | `data_generator/data_synthesizer.py` |
| Engineer historical data for SCD Type 2 | Synthesizer (engineered history), `dim_employee` |
| Load the data into a MySQL staging schema | `scripts/import_staging_csvs.py`, `hr_staging` |
| Normalized OLTP design with an ER diagram | `hr_oltp`, ER diagram |
| Star schema with surrogate keys and an SCD2 employee dimension | `hr_dw`, dimensional model diagram |
| DDL, DML, stored procedures, CTEs and window functions | `database/enterprise_employee_analytics.sql` |
| ETL from OLTP to the warehouse with correct SCD2 handling | `src/etl/pipeline.py`, `scripts/run_oltp_to_olap.py` |
| Singleton connection class, entity classes, data access layer, error handling | `src/` |
| Forms for employees, projects and reviews, with a department change creating an SCD2 update | `pages/`, `src/services/hr_service.py` |
| Interactive charts: year-over-year, top performers with `DENSE_RANK()`, attrition and bottlenecks | Analytics dashboard page |
| Feature branches and Pull Requests on GitHub | [Version control workflow](#version-control-workflow) |
| Public deployment on Streamlit Community Cloud | [Deployment](#deployment) |

## Troubleshooting

| Message | Likely cause |
| --- | --- |
| `Missing database settings` | `.env` is missing, misnamed, or not in the project root |
| `CA certificate not found` | The path in `.env` does not match the real file |
| Connection timeout or access denied | Aiven restricts allowed IP addresses; add yours in the Aiven service settings |
| `ModuleNotFoundError: No module named 'src'` | A script was run from the `scripts/` folder; run it from the repository root |
| Warehouse sync shows many pending changes | OLTP and warehouse data disagree; review the numbers before running a full sync |
| MySQL error 1267 (illegal mix of collations) | Text compared across schemas with different collations; the ETL already applies an explicit collation, so check any custom SQL |

## Design decisions, assumptions and limitations

- **ETL as Python-orchestrated SQL.** The OLTP-to-OLAP movement is set-based SQL run by the `ETLPipeline`
  classes, which allows one transaction, idempotent re-runs and single-record syncs from the UI. The stored
  procedures in the SQL file serve the analytics layer.
- **Pure star schema, deliberately denormalized.** Department names are stored as attributes in `dim_employee`
  and `dim_project`, so dimensions never reference each other. In `dim_employee` the department is a tracked
  SCD2 attribute: a department change must create a new version. The fact table also keeps `department_sk`,
  resolved from the employee version valid on the review date, so department-level analysis needs no extra join.
- **One snapshot becomes history.** The IBM data has no history, so SCD2 versions are engineered by the
  synthesizer for a configurable subset of employees.
- **Manager hierarchy.** The source data has no manager identifiers, so `employees.manager_id` stays empty
  until a valid mapping is supplied.
- **Assignment dates.** The source has no assignment end date, so total allocation per employee should be
  interpreted with care.
- **Project assignments.** Employees can be assigned to projects in the app, but not yet removed or moved
  between projects.
- **Synthetic data.** All names, emails and records are generated and must not be represented as real.
- **Shared database.** The deployed app's forms write to the shared database, so treat the public URL with
  care and clean up any test records you create.
