"""OLTP (hr_oltp) -> Data Warehouse (hr_dw) pipeline.

Pipeline order (each step is idempotent - running twice changes nothing):

    1. DepartmentDimLoader   hr_oltp.departments          -> dim_department      (Type 1)
    2. ProjectDimLoader      hr_oltp.projects             -> dim_project         (Type 1)
    3. DateDimLoader         hr_oltp.performance_reviews  -> dim_date (missing days)
    4. EmployeeSCD2Loader    hr_oltp.employees            -> dim_employee        (Type 2)
    5. FactLoader            hr_oltp.performance_reviews  -> fact_performance_reviews

Pure star schema: dim_employee and dim_project store ``department_name`` directly (no foreign key
to dim_department).  Only the fact table holds ``department_sk``; the fact loader resolves it from the
employee version's department name.

All SQL is set-based (no row-by-row Python), so it scales to 100k+ rows.  No table is
ever dropped, truncated or replaced.  Everything for one run happens in ONE transaction.

SCD Type 2 rules (match the generator + DDL in the project doc)
    * tracked attributes : department_name, job_role, job_level, monthly_income
    * old row            : end_date = change_date - 1 day, is_current = 0
    * new row            : NEW employee_sk, start_date = change_date,
                           end_date = 2099-12-31, is_current = 1, change_reason filled
    * same-day correction: if the current version started today, it is corrected in place
      (a closed version would otherwise violate CHECK end_date >= start_date)
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional

from sqlalchemy.engine import Connection

from src.database.db_manager import DW_SCHEMA, OLTP_SCHEMA, DatabaseConnection
from src.exceptions import DatabaseError, ETLError

logger = logging.getLogger(__name__)

HIGH_DATE = "2099-12-31"

# hr_oltp and hr_dw can store text with different collations (the new hr_dw tables use the server default,
# utf8mb4_0900_ai_ci, while hr_oltp may use utf8mb4_unicode_ci).  Comparing such columns raises MySQL error
# 1267 "Illegal mix of collations".  An explicit COLLATE on one operand always wins, so every text comparison
# that crosses the two schemas goes through ``ci()``.  Numeric / date comparisons never need it.
COLLATION = "utf8mb4_unicode_ci"
TEXT_TYPES = {"char", "varchar", "tinytext", "text", "mediumtext", "longtext", "enum", "set"}


def ci(expr: str) -> str:
    """Return ``expr`` with the pipeline's explicit collation (text expressions only)."""
    return f"{expr} COLLATE {COLLATION}"
TRANSIENT_MYSQL_CODES = {1205, 1213, 2006, 2013}  # lock wait, deadlock, server gone away, lost connection


# --------------------------------------------------------------------------- #
# Result object
# --------------------------------------------------------------------------- #
@dataclass
class SyncReport:
    """What one ETL step did."""

    step: str
    inserted: int = 0
    updated: int = 0
    closed: int = 0
    skipped: int = 0
    notes: List[str] = field(default_factory=list)

    @property
    def changed(self) -> int:
        return self.inserted + self.updated + self.closed

    def as_dict(self) -> Dict[str, Any]:
        return {"step": self.step, "inserted": self.inserted, "updated": self.updated,
                "closed": self.closed, "skipped": self.skipped, "notes": "; ".join(self.notes)}


# --------------------------------------------------------------------------- #
# Loader base
# --------------------------------------------------------------------------- #
class BaseLoader(DatabaseConnection):
    """One pipeline step. Subclasses implement ``run``."""

    step_name = "base"

    def run(self, conn: Connection, **filters: Any) -> SyncReport:  # pragma: no cover - abstract
        raise NotImplementedError


# --------------------------------------------------------------------------- #
# 1. Departments (Type 1)
# --------------------------------------------------------------------------- #
class DepartmentDimLoader(BaseLoader):
    step_name = "dim_department"

    def run(self, conn: Connection, **filters: Any) -> SyncReport:
        report = SyncReport(self.step_name)
        report.inserted = self.execute(
            f"""
            INSERT INTO {DW_SCHEMA}.dim_department (department_name, source_department_id)
            SELECT d.department_name, d.department_id
            FROM {OLTP_SCHEMA}.departments d
            WHERE NOT EXISTS (SELECT 1 FROM {DW_SCHEMA}.dim_department x
                              WHERE x.department_name = {ci('d.department_name')})
            """, conn=conn)
        report.updated = self.execute(
            f"""
            UPDATE {DW_SCHEMA}.dim_department dd
            JOIN {OLTP_SCHEMA}.departments d ON {ci('d.department_name')} = dd.department_name
            SET dd.source_department_id = d.department_id
            WHERE NOT (dd.source_department_id <=> d.department_id)
            """, conn=conn)
        return report


# --------------------------------------------------------------------------- #
# 2. Projects (Type 1)
# --------------------------------------------------------------------------- #
class ProjectDimLoader(BaseLoader):
    step_name = "dim_project"

    def run(self, conn: Connection, project_id: Optional[int] = None, **_: Any) -> SyncReport:
        report = SyncReport(self.step_name)
        flt = "AND p.project_id = :pid" if project_id is not None else ""
        params = {"pid": project_id} if project_id is not None else {}
        report.inserted = self.execute(
            f"""
            INSERT INTO {DW_SCHEMA}.dim_project
                (project_id, project_name, department_name, start_date, end_date, project_status, budget)
            SELECT p.project_id, p.project_name, od.department_name, p.start_date, p.end_date,
                   p.project_status, p.budget
            FROM {OLTP_SCHEMA}.projects p
            JOIN {OLTP_SCHEMA}.departments od ON od.department_id = p.department_id
            WHERE NOT EXISTS (SELECT 1 FROM {DW_SCHEMA}.dim_project x WHERE x.project_id = p.project_id) {flt}
            """, params, conn)
        report.updated = self.execute(
            f"""
            UPDATE {DW_SCHEMA}.dim_project dp
            JOIN {OLTP_SCHEMA}.projects p ON p.project_id = dp.project_id
            JOIN {OLTP_SCHEMA}.departments od ON od.department_id = p.department_id
            SET dp.project_name = p.project_name, dp.department_name = od.department_name,
                dp.start_date = p.start_date, dp.end_date = p.end_date,
                dp.project_status = p.project_status, dp.budget = p.budget
            WHERE NOT (dp.project_name <=> {ci('p.project_name')}
                       AND dp.department_name <=> {ci('od.department_name')}
                       AND dp.start_date <=> p.start_date AND dp.end_date <=> p.end_date
                       AND dp.project_status <=> {ci('p.project_status')} AND dp.budget <=> p.budget) {flt}
            """, params, conn)
        return report


# --------------------------------------------------------------------------- #
# 3. Dates
# --------------------------------------------------------------------------- #
class DateDimLoader(BaseLoader):
    step_name = "dim_date"

    def run(self, conn: Connection, review_id: Optional[int] = None, **_: Any) -> SyncReport:
        report = SyncReport(self.step_name)
        flt = "AND r.review_id = :rid" if review_id is not None else ""
        params = {"rid": review_id} if review_id is not None else {}
        report.inserted = self.execute(
            f"""
            INSERT INTO {DW_SCHEMA}.dim_date
                (date_sk, full_date, day_number, month_number, month_name, quarter_number, year_number, weekday_name)
            SELECT DISTINCT CAST(DATE_FORMAT(r.review_date, '%Y%m%d') AS UNSIGNED), r.review_date,
                   DAY(r.review_date), MONTH(r.review_date), MONTHNAME(r.review_date),
                   QUARTER(r.review_date), YEAR(r.review_date), DAYNAME(r.review_date)
            FROM {OLTP_SCHEMA}.performance_reviews r
            WHERE NOT EXISTS (SELECT 1 FROM {DW_SCHEMA}.dim_date x WHERE x.full_date = r.review_date) {flt}
            """, params, conn)
        return report


# --------------------------------------------------------------------------- #
# 4. Employees - SCD Type 2
# --------------------------------------------------------------------------- #
class EmployeeSCD2Loader(BaseLoader):
    step_name = "dim_employee (SCD2)"

    # dim_employee columns handled explicitly; everything else is copied / refreshed generically
    _SPECIAL = {"employee_sk", "employee_number", "department_name", "job_level", "job_role", "monthly_income",
                "start_date", "end_date", "is_current", "change_reason", "employee_name", "employee_email",
                "synthetic_hire_date"}
    _INCOME_CANDIDATES = ("monthly_income", "monthlyincome")

    def __init__(self) -> None:
        super().__init__()
        self._ctx: Optional[Dict[str, Any]] = None

    # -- schema discovery (the live DDL is the source of truth) ------------------ #
    def _context(self) -> Dict[str, Any]:
        if self._ctx is None:
            dim = self.table_columns(DW_SCHEMA, "dim_employee")
            oltp = self.table_columns(OLTP_SCHEMA, "employees")
            oltp_lower = {c.lower(): c for c in oltp}
            income = next((oltp_lower[c] for c in self._INCOME_CANDIDATES if c in oltp_lower), None)
            # attributes with the same name AND the same data type on both sides are copied / refreshed
            common = [c for c in dim if c.lower() in oltp_lower and c.lower() not in self._SPECIAL
                      and dim[c] == oltp[oltp_lower[c.lower()]]]
            self._ctx = {"dim": dim, "income": income, "common": common,
                         "has_email": "employee_email" in dim, "has_name": "employee_name" in dim,
                         "has_hire": "synthetic_hire_date" in dim}
        return self._ctx

    @property
    def tracks_income(self) -> bool:
        return self._context()["income"] is not None

    # -- SQL fragments ---------------------------------------------------------- #
    @staticmethod
    def _joins() -> str:
        return (f"JOIN {OLTP_SCHEMA}.departments od ON od.department_id = e.department_id "
                f"JOIN {OLTP_SCHEMA}.job_roles jr ON jr.job_role_id = e.job_role_id")

    def _changed(self) -> str:
        income = self._context()["income"]
        cmp_income = f" AND de.monthly_income <=> e.`{income}`" if income else ""
        return (f"NOT (de.department_name <=> {ci('od.department_name')} "
                f"AND de.job_role <=> {ci('jr.job_title')} "
                f"AND de.job_level <=> e.job_level{cmp_income})")

    @staticmethod
    def _flt(employee_number: Optional[int]) -> str:
        return "AND e.employee_number = :emp" if employee_number is not None else ""

    # -- preview ---------------------------------------------------------------- #
    def pending(self, conn: Optional[Connection] = None, employee_number: Optional[int] = None) -> Dict[str, int]:
        """How many versions / new employees the next run would create (no writes)."""
        p = {"emp": employee_number} if employee_number is not None else {}
        flt = self._flt(employee_number)
        changed = self.fetch_one(
            f"SELECT COUNT(*) AS n FROM {DW_SCHEMA}.dim_employee de "
            f"JOIN {OLTP_SCHEMA}.employees e ON e.employee_number = de.employee_number {self._joins()} "
            f"WHERE de.is_current = 1 AND {self._changed()} {flt}", p, conn)
        new = self.fetch_one(
            f"SELECT COUNT(*) AS n FROM {OLTP_SCHEMA}.employees e WHERE NOT EXISTS "
            f"(SELECT 1 FROM {DW_SCHEMA}.dim_employee x WHERE x.employee_number = e.employee_number) {flt}", p, conn)
        return {"changed_employees": int(changed["n"]), "new_employees": int(new["n"])}

    # -- run -------------------------------------------------------------------- #
    def run(self, conn: Connection, employee_number: Optional[int] = None,
            change_date: Optional[date] = None, **_: Any) -> SyncReport:
        ctx = self._context()
        report = SyncReport(self.step_name)
        today = change_date or date.today()
        flt = self._flt(employee_number)
        params: Dict[str, Any] = {"cd": today}
        if employee_number is not None:
            params["emp"] = employee_number
        income = ctx["income"]
        changed = self._changed()
        joins = self._joins()
        src_join = f"JOIN {OLTP_SCHEMA}.employees e ON e.employee_number = de.employee_number {joins}"

        # (a) same-day correction in place --------------------------------------------------
        set_income = f", de.monthly_income = e.`{income}`" if income else ""
        report.updated += self.execute(
            f"UPDATE {DW_SCHEMA}.dim_employee de {src_join} "
            f"SET de.department_name = od.department_name, de.job_role = jr.job_title, de.job_level = e.job_level{set_income} "
            f"WHERE de.is_current = 1 AND de.start_date >= :cd AND {changed} {flt}", params, conn)

        # (b) close the current version whose tracked attributes changed ----------------------
        report.closed = self.execute(
            f"UPDATE {DW_SCHEMA}.dim_employee de {src_join} "
            f"SET de.end_date = DATE_SUB(:cd, INTERVAL 1 DAY), de.is_current = 0 "
            f"WHERE de.is_current = 1 AND de.start_date < :cd AND {changed} {flt}", params, conn)

        # (c) open the new version for every employee left without a current row ----------------
        report.inserted += self._insert_new_versions(conn, params, flt)

        # (d) brand-new employees (no version at all) ---------------------------------------------
        report.inserted += self._insert_new_employees(conn, params, flt)

        # (e) Type 1 refresh of non-tracked attributes (name, e-mail, attrition ...) -------------
        report.updated += self._refresh_untracked(conn, params, flt)

        if report.changed:
            logger.info("SCD2: %s", report.as_dict())
        return report

    # -- (c) ---------------------------------------------------------------------------------------
    def _insert_new_versions(self, conn: Connection, params: Dict[str, Any], flt: str) -> int:
        ctx = self._context()
        income = ctx["income"]
        income_expr = f"e.`{income}`" if income else "old.monthly_income"
        reason_parts = [
            f"CASE WHEN NOT (old.department_name <=> {ci('od.department_name')}) THEN 'Department change' END",
            f"CASE WHEN NOT (old.job_role <=> {ci('jr.job_title')}) THEN 'Job role change' END",
            "CASE WHEN NOT (old.job_level <=> e.job_level) THEN 'Job level change' END",
        ]
        if income:
            reason_parts.append(f"CASE WHEN NOT (old.monthly_income <=> e.`{income}`) THEN 'Salary change' END")
        reason = f"LEFT(CONCAT_WS(', ', {', '.join(reason_parts)}), 100)"

        cols = ["employee_number", "department_name", "job_level", "job_role", "monthly_income",
                "start_date", "end_date", "is_current", "change_reason"]
        exprs = ["e.employee_number", "od.department_name", "e.job_level", "jr.job_title", income_expr,
                 ":cd", f"'{HIGH_DATE}'", "1", reason]
        if ctx["has_name"]:
            cols.append("employee_name"); exprs.append("e.employee_name")
        if ctx["has_email"]:
            cols.append("employee_email"); exprs.append("e.email")
        if ctx["has_hire"]:
            cols.append("synthetic_hire_date"); exprs.append("old.synthetic_hire_date")
        for c in ctx["common"]:
            cols.append(c); exprs.append(f"e.`{c}`")
        # any other dim column (age bands, rates ...) is carried forward from the previous version
        handled = {c.lower() for c in cols} | {"employee_sk"}
        for c in ctx["dim"]:
            if c.lower() not in handled:
                cols.append(c); exprs.append(f"old.`{c}`")

        col_sql = ", ".join(f"`{c}`" for c in cols)
        return self.execute(
            f"INSERT INTO {DW_SCHEMA}.dim_employee ({col_sql}) "
            f"SELECT {', '.join(exprs)} FROM {OLTP_SCHEMA}.employees e {self._joins()} "
            f"JOIN {DW_SCHEMA}.dim_employee old ON old.employee_number = e.employee_number "
            f"AND old.is_current = 0 AND old.end_date = DATE_SUB(:cd, INTERVAL 1 DAY) "
            f"WHERE NOT EXISTS (SELECT 1 FROM {DW_SCHEMA}.dim_employee c "
            f"WHERE c.employee_number = e.employee_number AND c.is_current = 1) {flt}", params, conn)

    # -- (d) ---------------------------------------------------------------------------------------
    def _insert_new_employees(self, conn: Connection, params: Dict[str, Any], flt: str) -> int:
        ctx = self._context()
        income = ctx["income"]
        cols = ["employee_number", "department_name", "job_level", "job_role", "start_date", "end_date",
                "is_current", "change_reason"]
        exprs = ["e.employee_number", "od.department_name", "e.job_level", "jr.job_title",
                 "COALESCE(e.hire_date, :cd)", f"'{HIGH_DATE}'", "1", "'New employee'"]
        if income:
            cols.append("monthly_income"); exprs.append(f"e.`{income}`")
        if ctx["has_name"]:
            cols.append("employee_name"); exprs.append("e.employee_name")
        if ctx["has_email"]:
            cols.append("employee_email"); exprs.append("e.email")
        if ctx["has_hire"]:
            cols.append("synthetic_hire_date"); exprs.append("e.hire_date")
        for c in ctx["common"]:
            cols.append(c); exprs.append(f"e.`{c}`")
        col_sql = ", ".join(f"`{c}`" for c in cols)
        return self.execute(
            f"INSERT INTO {DW_SCHEMA}.dim_employee ({col_sql}) "
            f"SELECT {', '.join(exprs)} FROM {OLTP_SCHEMA}.employees e {self._joins()} "
            f"WHERE NOT EXISTS (SELECT 1 FROM {DW_SCHEMA}.dim_employee x "
            f"WHERE x.employee_number = e.employee_number) {flt}", params, conn)

    # -- (e) ---------------------------------------------------------------------------------------
    def _refresh_untracked(self, conn: Connection, params: Dict[str, Any], flt: str) -> int:
        ctx = self._context()
        pairs: List[tuple] = []
        if ctx["has_name"]:
            pairs.append(("employee_name", "e.employee_name"))
        if ctx["has_email"]:
            pairs.append(("employee_email", "e.email"))
        pairs += [(c, f"e.`{c}`") for c in ctx["common"]]
        if not pairs:
            return 0
        is_text = lambda col: ctx["dim"].get(col, "") in TEXT_TYPES  # noqa: E731
        sets = ", ".join(f"de.`{c}` = {src}" for c, src in pairs)
        same = " AND ".join(f"de.`{c}` <=> {ci(src) if is_text(c) else src}" for c, src in pairs)
        p = {k: v for k, v in params.items() if k == "emp"}
        return self.execute(
            f"UPDATE {DW_SCHEMA}.dim_employee de "
            f"JOIN {OLTP_SCHEMA}.employees e ON e.employee_number = de.employee_number "
            f"SET {sets} WHERE de.is_current = 1 AND NOT ({same}) {flt}", p, conn)


# --------------------------------------------------------------------------- #
# 5. Facts
# --------------------------------------------------------------------------- #
class FactLoader(BaseLoader):
    step_name = "fact_performance_reviews"

    def run(self, conn: Connection, review_id: Optional[int] = None, **_: Any) -> SyncReport:
        report = SyncReport(self.step_name)
        flt = "AND r.review_id = :rid" if review_id is not None else ""
        params = {"rid": review_id} if review_id is not None else {}
        # CTE + ROW_NUMBER guarantees exactly ONE employee version per review even if
        # validity ranges ever overlap (the DDL does not enforce non-overlap).
        report.inserted = self.execute(
            f"""
            INSERT INTO {DW_SCHEMA}.fact_performance_reviews
                (source_review_id, employee_sk, project_sk, department_sk, review_date_sk,
                 performance_rating, job_satisfaction, review_score, review_count)
            WITH matched AS (
                SELECT r.review_id, de.employee_sk, dd.department_sk, dp.project_sk, dt.date_sk,
                       r.performance_rating, r.job_satisfaction, r.review_score,
                       ROW_NUMBER() OVER (PARTITION BY r.review_id
                                          ORDER BY de.start_date DESC, de.employee_sk DESC) AS rn
                FROM {OLTP_SCHEMA}.performance_reviews r
                JOIN {OLTP_SCHEMA}.employees e ON e.employee_id = r.employee_id
                JOIN {DW_SCHEMA}.dim_employee de ON de.employee_number = e.employee_number
                     AND r.review_date BETWEEN de.start_date AND de.end_date
                JOIN {DW_SCHEMA}.dim_department dd ON dd.department_name = {ci('de.department_name')}
                JOIN {DW_SCHEMA}.dim_project dp ON dp.project_id = r.project_id
                JOIN {DW_SCHEMA}.dim_date dt ON dt.full_date = r.review_date
                WHERE NOT EXISTS (SELECT 1 FROM {DW_SCHEMA}.fact_performance_reviews f
                                  WHERE f.source_review_id = r.review_id) {flt}
            )
            SELECT review_id, employee_sk, project_sk, department_sk, date_sk,
                   performance_rating, job_satisfaction, review_score, 1
            FROM matched WHERE rn = 1
            """, params, conn)
        left = self.fetch_one(
            f"SELECT COUNT(*) AS n FROM {OLTP_SCHEMA}.performance_reviews r WHERE NOT EXISTS "
            f"(SELECT 1 FROM {DW_SCHEMA}.fact_performance_reviews f WHERE f.source_review_id = r.review_id) {flt}",
            params, conn)
        report.skipped = int(left["n"]) if left else 0
        if report.skipped:
            report.notes.append(f"{report.skipped} review(s) have no matching employee version / department / project / date")
        return report


# --------------------------------------------------------------------------- #
# Orchestrator
# --------------------------------------------------------------------------- #
class ETLPipeline(DatabaseConnection):
    """Runs the loaders in order, in one transaction, with retries on lock/deadlock errors."""

    MAX_ATTEMPTS = 3

    def __init__(self) -> None:
        super().__init__()
        self.departments = DepartmentDimLoader()
        self.projects = ProjectDimLoader()
        self.dates = DateDimLoader()
        self.employees = EmployeeSCD2Loader()
        self.facts = FactLoader()

    # -- public API ------------------------------------------------------------ #
    def run_full_sync(self) -> List[SyncReport]:
        return self._run("full sync", [(self.departments, {}), (self.projects, {}), (self.dates, {}),
                                       (self.employees, {}), (self.facts, {})])

    def sync_employee(self, employee_number: int) -> List[SyncReport]:
        """Called by the UI after an employee is created / changed -> SCD2 update."""
        return self._run(f"employee {employee_number}",
                         [(self.departments, {}), (self.employees, {"employee_number": employee_number})])

    def sync_project(self, project_id: int) -> List[SyncReport]:
        return self._run(f"project {project_id}", [(self.departments, {}), (self.projects, {"project_id": project_id})])

    def sync_review(self, review_id: int) -> List[SyncReport]:
        """Called by the UI after a review is submitted -> new fact row."""
        return self._run(f"review {review_id}",
                         [(self.departments, {}), (self.projects, {}), (self.dates, {"review_id": review_id}),
                          (self.facts, {"review_id": review_id})])

    def pending_changes(self) -> Dict[str, int]:
        """Read-only preview of what a full sync would do."""
        out = self.employees.pending()
        out["reviews_not_in_fact"] = int(self.fetch_one(
            f"SELECT COUNT(*) AS n FROM {OLTP_SCHEMA}.performance_reviews r WHERE NOT EXISTS "
            f"(SELECT 1 FROM {DW_SCHEMA}.fact_performance_reviews f WHERE f.source_review_id = r.review_id)")["n"])
        return out

    def validate_scd2(self) -> Dict[str, int]:
        """Data-quality checks for rules the DDL does NOT enforce. Every value should be 0."""
        q = lambda sql: int(self.fetch_one(sql)["n"])  # noqa: E731
        dim = f"{DW_SCHEMA}.dim_employee"
        return {
            "employees_with_no_current_row": q(
                f"SELECT COUNT(*) AS n FROM (SELECT employee_number FROM {dim} GROUP BY employee_number "
                "HAVING SUM(is_current) = 0) t"),
            "employees_with_multiple_current_rows": q(
                f"SELECT COUNT(*) AS n FROM (SELECT employee_number FROM {dim} GROUP BY employee_number "
                "HAVING SUM(is_current) > 1) t"),
            "overlapping_version_pairs": q(
                f"SELECT COUNT(*) AS n FROM {dim} a JOIN {dim} b ON a.employee_number = b.employee_number "
                "AND a.employee_sk < b.employee_sk AND a.start_date <= b.end_date AND b.start_date <= a.end_date"),
            "oltp_employees_missing_in_dw": q(
                f"SELECT COUNT(*) AS n FROM {OLTP_SCHEMA}.employees e WHERE NOT EXISTS "
                f"(SELECT 1 FROM {dim} x WHERE x.employee_number = e.employee_number)"),
            "employee_versions_with_unknown_department": q(
                f"SELECT COUNT(*) AS n FROM {dim} de WHERE NOT EXISTS "
                f"(SELECT 1 FROM {DW_SCHEMA}.dim_department d WHERE d.department_name = {ci('de.department_name')})"),
            "projects_with_unknown_department": q(
                f"SELECT COUNT(*) AS n FROM {DW_SCHEMA}.dim_project p WHERE p.department_name IS NOT NULL AND NOT EXISTS "
                f"(SELECT 1 FROM {DW_SCHEMA}.dim_department d WHERE d.department_name = {ci('p.department_name')})"),
            "fact_department_differs_from_employee_version": q(
                f"SELECT COUNT(*) AS n FROM {DW_SCHEMA}.fact_performance_reviews f "
                f"JOIN {dim} de ON de.employee_sk = f.employee_sk "
                f"JOIN {DW_SCHEMA}.dim_department d ON d.department_name = {ci('de.department_name')} "
                "WHERE f.department_sk <> d.department_sk"),
            "reviews_missing_in_fact": q(
                f"SELECT COUNT(*) AS n FROM {OLTP_SCHEMA}.performance_reviews r WHERE NOT EXISTS "
                f"(SELECT 1 FROM {DW_SCHEMA}.fact_performance_reviews f WHERE f.source_review_id = r.review_id)"),
        }

    # -- engine ---------------------------------------------------------------------- #
    def _run(self, label: str, steps: List[tuple]) -> List[SyncReport]:
        last: Optional[Exception] = None
        for attempt in range(1, self.MAX_ATTEMPTS + 1):
            try:
                started = time.perf_counter()
                reports: List[SyncReport] = []
                with self.transaction() as conn:
                    for loader, kwargs in steps:
                        reports.append(loader.run(conn, **kwargs))
                logger.info("ETL %s finished in %.2fs", label, time.perf_counter() - started)
                return reports
            except DatabaseError as exc:
                last = exc
                if exc.code in TRANSIENT_MYSQL_CODES and attempt < self.MAX_ATTEMPTS:
                    wait = 0.5 * 2 ** (attempt - 1)
                    logger.warning("ETL %s attempt %s failed (%s); retrying in %.1fs", label, attempt, exc, wait)
                    time.sleep(wait)
                    continue
                break
        raise ETLError(f"ETL {label} failed and was rolled back: {last}") from last