# Application Layer: OOP Backend, ETL Pipeline and Streamlit App

This section covers the Python application that sits on top of the databases: an object-oriented
backend, the OLTP-to-warehouse ETL pipeline, and the Streamlit web app (data entry plus analytics).

## How the pieces fit together

```
 Streamlit forms ──► Managers (OLTP CRUD) ──► hr_oltp   (commit)
                                                 │
                                                 ▼
                                   ETL pipeline (set-based SQL)
                                                 │
                                                 ▼
 Streamlit dashboard ◄── AnalyticsManager ◄── hr_dw     (star schema)
```

1. A form saves the change to **hr_oltp** in its own transaction.
2. `HRService` then runs the matching ETL step, which copies the change into **hr_dw**.
3. If a department, job role, job level or monthly income changed, the ETL closes the employee's current
   history row and opens a new one (**SCD Type 2**). History is never overwritten.
4. The dashboards read only from **hr_dw**.

If the ETL step fails after the OLTP save, the data stays saved. The user sees a warning and can retry from
the **Warehouse sync** page. Nothing is lost and nothing is half-written.

## Project structure (application layer)

| Path | Purpose |
|---|---|
| `src/database/db_manager.py` | `DatabaseConnection`: thread-safe Singleton that owns one pooled, SSL-verified SQLAlchemy engine. Provides query, transaction and schema-inspection helpers. |
| `src/exceptions.py` | Exception hierarchy (`DatabaseError`, `ValidationError`, `DuplicateRecordError`, `ETLError`, ...) so the UI never deals with driver errors directly. |
| `src/models/` | `Employee`, `Project`, `Review` entity classes. Fields are validated whenever they are set (type, range, email format, dates). |
| `src/managers/` | Data access layer. `EmployeeManager`, `ProjectManager`, `ReviewManager` handle CRUD on `hr_oltp`. `AnalyticsManager` runs read-only queries on `hr_dw`. All inherit `DatabaseConnection`. |
| `src/etl/pipeline.py` | `ETLPipeline` and its loaders (dimensions, SCD Type 2 employees, facts, data-quality checks). |
| `src/services/hr_service.py` | `HRService`: saves to OLTP, then triggers the matching ETL step. |
| `streamlit_app.py`, `pages/`, `ui/` | The Streamlit app. |
| `tests/test_entities.py` | Unit tests for the entity classes (no database needed). |

## OOP backend (Phase 3)

- **Singleton connection:** `DatabaseConnection` uses a thread-safe metaclass so the whole app shares one
  connection pool. Manager and ETL classes inherit from it; each is its own singleton, but all share the
  single engine. The pool uses `pool_pre_ping` and recycles connections.
- **Encapsulated entities:** each attribute is a validating descriptor. Invalid values raise
  `ValidationError` at assignment time, and behaviour lives on the class (for example
  `Employee.promote()`, `Employee.give_raise()`, `Project.is_overdue()`, `Review.rating_label`).
- **Data access layer:** managers wrap every operation in `try/except` and translate database errors into the
  project's exception types. Writes run inside transactions that roll back on any error. Tables whose primary
  key is not `AUTO_INCREMENT` (projects, assignments, reviews) get their next id inside the same transaction.
- **Schema-aware inserts:** managers read the live column list and skip any column the table does not have,
  logging a warning, instead of failing.

## ETL pipeline

Run order (every step is idempotent, so running it twice changes nothing):

| Step | Source | Target | Type |
|---|---|---|---|
| 1 | `hr_oltp.departments` | `dim_department` | Type 1 |
| 2 | `hr_oltp.projects` | `dim_project` | Type 1 |
| 3 | `hr_oltp.performance_reviews` | `dim_date` (missing days only) | Insert |
| 4 | `hr_oltp.employees` | `dim_employee` | **SCD Type 2** |
| 5 | `hr_oltp.performance_reviews` | `fact_performance_reviews` | Insert |

**SCD Type 2 rules**

- Tracked attributes: department, job role, job level, monthly income.
- When one changes, the current row gets `end_date = change_date - 1 day` and `is_current = 0`. A new row is
  inserted with a **new surrogate key**, `start_date = change_date`, `end_date = 2099-12-31`,
  `is_current = 1`, and a `change_reason` such as `Department change` or `Salary change`.
- If a change is made on the same day the current version started, that version is corrected in place.
  Closing it would create an invalid range (`end_date < start_date`).
- Non-tracked attributes (name, email, attrition, and similar) are refreshed in place (Type 1).
- New employees get a first row with the reason `New employee`.

**Fact loading**

- Each review is linked to the employee version that was valid **on the review date**, so old reviews keep
  pointing at the old department. A CTE with `ROW_NUMBER()` guarantees exactly one version per review even if
  date ranges ever overlapped.

**Safety and quality**

- All SQL is set-based (no row-by-row Python). Tables are never dropped, truncated or replaced.
- One run is one transaction: either everything is applied or nothing is. Lock-wait and deadlock errors are
  retried up to three times.
- `ETLPipeline.validate_scd2()` checks rules the database does not enforce: every employee has exactly one
  current row, no overlapping version ranges, no OLTP employees missing from the warehouse, no reviews missing
  from the fact table. Every value should be `0`.
- `ETLPipeline.pending_changes()` previews what a full sync would do without writing anything.

**Entry points**

```python
etl = ETLPipeline()
etl.sync_employee(employee_number)   # after an employee is created or changed
etl.sync_review(review_id)           # after a review is submitted
etl.sync_project(project_id)         # after a project is created
etl.run_full_sync()                  # everything
```

## Streamlit app (Phase 4)

| Page | What it does |
|---|---|
| **Home** | Warehouse KPIs and a short explanation of the data flow. |
| **Onboard employee** | Form that creates an employee in OLTP and their first warehouse record. |
| **Update employee** | Change department, job role, level, salary or status. A tracked change creates an SCD Type 2 version. Shows a version timeline. |
| **Projects** | Create projects, assign employees (with allocation %), and list projects. |
| **Reviews** | Submit a performance review. It becomes a fact row linked to the correct employee version. |
| **Analytics dashboard** | Four tabs, described below. Reads only from the warehouse. |
| **Warehouse sync** | Pending work, manual full sync, data-quality checks, and any employee's version history. |

**Dashboard tabs**

| Tab | Content | SQL technique |
|---|---|---|
| Year-over-year trends | Average score by year and by department, with change versus the previous year | CTE, `LAG()` |
| Top performers | Top N employees per department, with a minimum-reviews filter so one lucky review cannot win | CTE, `DENSE_RANK() OVER (PARTITION BY department ...)` |
| Attrition risk | Attrition rate by department and job role, plus a rule-based risk score for all current employees who have not left | CTE, `ROW_NUMBER()`, `LAG()`, window `AVG()` |
| Project bottlenecks | Overdue projects, and open projects in the bottom quarter by average review score | CTE, `NTILE(4)` |

**Attrition risk score (0-100),** taken from each employee's latest review: job satisfaction of 2 or lower
(40 points), review score fell by 10 or more points (20), score below the department average (20), monthly
income below 80% of the department average (20). Bands: Low is up to 20, Medium up to 40, High above 40.
Employees whose attrition flag is already "Yes" are excluded.

## Setup and running locally

Requirements: Python 3.10 or newer.

```bash
python -m venv .venv
# Windows:  .venv\Scripts\Activate.ps1      macOS/Linux:  source .venv/bin/activate
pip install -r requirements.txt
```

Create a `.env` file in the project root (copy `.env.example`):

```
MYSQL_HOST=your-aiven-hostname
MYSQL_PORT=your-aiven-port
MYSQL_USER=avnadmin
MYSQL_PASSWORD=your-aiven-password
MYSQL_CA_CERT=certificates/ca.pem
```

Put the Aiven CA certificate at `certificates/ca.pem`. The `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD` and
`DB_SSL_CA` names are also accepted. `.env` and the certificate are git-ignored and must never be committed.

Run the unit tests (no database required) and then the app:

```bash
python -m pytest tests -q
streamlit run streamlit_app.py
```

The app opens at http://localhost:8501. The sidebar shows the database connection status.

## Deploying to Streamlit Community Cloud

1. Push the code to GitHub and create a new app with `streamlit_app.py` as the main file.
2. In **App settings → Secrets**, add the same values as the `.env` file (see
   `.streamlit/secrets.toml.example`).
3. Streamlit Cloud has no local certificate file, so paste the certificate text into the `DB_SSL_CA_PEM`
   secret instead of using a file path.
4. In the Aiven service settings, make sure connections from Streamlit Cloud are allowed.

## Troubleshooting

| Message | Likely cause |
|---|---|
| `Missing database settings` | `.env` is missing, misnamed, or not in the project root. |
| `CA certificate not found` | The path in `.env` does not match the real file. |
| Connection timeout or access denied | Aiven restricts allowed IP addresses. Add yours in the Aiven service settings. |
| Warehouse sync shows many pending changes | OLTP and warehouse data disagree. Review the numbers before running a full sync. |
