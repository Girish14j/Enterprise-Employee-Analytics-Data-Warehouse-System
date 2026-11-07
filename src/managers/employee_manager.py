"""CRUD for ``hr_oltp.employees`` plus the lookups the forms need."""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Tuple

import pandas as pd

from src.exceptions import (DatabaseError, DuplicateRecordError, IntegrityViolationError,
                            RecordNotFoundError, ValidationError)
from src.managers.base_manager import BaseManager
from src.models.entities import Employee


class EmployeeManager(BaseManager):
    TABLE = "employees"

    #: columns the UI / services may change on an existing employee
    UPDATABLE = {
        "first_name", "last_name", "email", "department_id", "job_role_id", "job_level",
        "monthly_income", "age", "gender", "marital_status", "education_field",
        "business_travel", "overtime", "attrition", "employment_status", "manager_id", "hire_date",
    }
    #: attributes that create a new SCD Type 2 version in dim_employee
    SCD2_FIELDS = ("department_id", "job_role_id", "job_level", "monthly_income")

    # ------------------------------------------------------------------ #
    # Lookups
    # ------------------------------------------------------------------ #
    @property
    def supports_income(self) -> bool:
        """True when ``hr_oltp.employees`` has a monthly_income column."""
        return "monthly_income" in self._existing_columns(self.OLTP, self.TABLE)

    def list_departments(self) -> List[Dict[str, Any]]:
        return self.fetch_all(f"SELECT department_id, department_name FROM {self.OLTP}.departments "
                              "ORDER BY department_name")

    def list_job_roles(self) -> List[Dict[str, Any]]:
        return self.fetch_all(f"SELECT job_role_id, job_title FROM {self.OLTP}.job_roles ORDER BY job_title")

    def distinct_values(self, column: str, limit: int = 25) -> List[str]:
        """Existing values of a categorical column (so forms offer exactly what the data uses)."""
        cols = self._existing_columns(self.OLTP, self.TABLE)
        if column.lower() not in cols:
            return []
        real = cols[column.lower()]
        rows = self.fetch_all(f"SELECT DISTINCT `{real}` AS v FROM {self.OLTP}.{self.TABLE} "
                              f"WHERE `{real}` IS NOT NULL ORDER BY 1 LIMIT {int(limit)}")
        return [str(r["v"]) for r in rows]

    def next_employee_number(self) -> int:
        row = self.fetch_one(f"SELECT COALESCE(MAX(employee_number), 0) + 1 AS n FROM {self.OLTP}.{self.TABLE}")
        return int(row["n"]) if row else 1

    # ------------------------------------------------------------------ #
    # Create
    # ------------------------------------------------------------------ #
    def create(self, employee: Employee) -> int:
        """Insert a new employee. Returns the new ``employee_id``."""
        employee.validate()
        row = self._filter_to_columns(employee.to_db_row(), self.OLTP, self.TABLE)
        cols = self._col_list(row)
        marks = ", ".join(f":{k}" for k in row)
        try:
            with self.transaction() as conn:
                if self.fetch_one(f"SELECT 1 FROM {self.OLTP}.{self.TABLE} WHERE employee_number = :n",
                                  {"n": employee.employee_number}, conn):
                    raise DuplicateRecordError(f"Employee number {employee.employee_number} already exists.")
                if self.fetch_one(f"SELECT 1 FROM {self.OLTP}.{self.TABLE} WHERE email = :e",
                                  {"e": employee.email}, conn):
                    raise DuplicateRecordError(f"Email {employee.email} is already in use.")
                new_id = self.insert(f"INSERT INTO {self.OLTP}.{self.TABLE} ({cols}) VALUES ({marks})", row, conn)
        except IntegrityViolationError as exc:
            raise ValidationError(f"Could not save the employee - check the department, job role and "
                                  f"manager exist. ({exc})") from exc
        self._log.info("Created employee_id=%s number=%s", new_id, employee.employee_number)
        return new_id

    # ------------------------------------------------------------------ #
    # Read
    # ------------------------------------------------------------------ #
    def get_by_id(self, employee_id: int) -> Employee:
        row = self.fetch_one(f"SELECT * FROM {self.OLTP}.{self.TABLE} WHERE employee_id = :i", {"i": employee_id})
        if not row:
            raise RecordNotFoundError(f"Employee id {employee_id} not found.")
        return Employee.from_row(row)

    def get_by_number(self, employee_number: int) -> Employee:
        row = self.fetch_one(f"SELECT * FROM {self.OLTP}.{self.TABLE} WHERE employee_number = :n",
                             {"n": employee_number})
        if not row:
            raise RecordNotFoundError(f"Employee number {employee_number} not found.")
        return Employee.from_row(row)

    def get_detail(self, employee_id: int) -> Dict[str, Any]:
        """Employee row joined with department and job title names."""
        row = self.fetch_one(
            f"SELECT e.*, d.department_name, jr.job_title FROM {self.OLTP}.{self.TABLE} e "
            f"JOIN {self.OLTP}.departments d ON d.department_id = e.department_id "
            f"JOIN {self.OLTP}.job_roles jr ON jr.job_role_id = e.job_role_id WHERE e.employee_id = :i",
            {"i": employee_id})
        if not row:
            raise RecordNotFoundError(f"Employee id {employee_id} not found.")
        return row

    def search(self, term: Optional[str] = None, department_id: Optional[int] = None,
               status: Optional[str] = None, limit: int = 50) -> pd.DataFrame:
        term = (term or "").strip() or None
        return self.fetch_df(
            f"SELECT e.employee_id, e.employee_number, e.employee_name, e.email, d.department_name, "
            f"jr.job_title, e.job_level, e.employment_status "
            f"FROM {self.OLTP}.{self.TABLE} e "
            f"JOIN {self.OLTP}.departments d ON d.department_id = e.department_id "
            f"JOIN {self.OLTP}.job_roles jr ON jr.job_role_id = e.job_role_id "
            "WHERE (:term IS NULL OR e.employee_name LIKE :like OR CAST(e.employee_number AS CHAR) = :term) "
            "AND (:dept IS NULL OR e.department_id = :dept) "
            "AND (:status IS NULL OR e.employment_status = :status) "
            f"ORDER BY e.employee_name LIMIT {max(1, min(int(limit), 500))}",
            {"term": term, "like": f"%{term}%" if term else None, "dept": department_id, "status": status})

    # ------------------------------------------------------------------ #
    # Update
    # ------------------------------------------------------------------ #
    def update(self, employee_id: int, changes: Mapping[str, Any]) -> Dict[str, Tuple[Any, Any]]:
        """Apply ``changes`` and return ``{field: (old, new)}`` for the values that really changed."""
        unknown = set(changes) - self.UPDATABLE
        if unknown:
            raise ValidationError(f"Field(s) cannot be updated: {', '.join(sorted(unknown))}")
        if not changes:
            raise ValidationError("Nothing to update.")
        probe = Employee(**dict(changes))  # validates every provided value
        clean = {k: getattr(probe, k) for k in changes}
        clean = self._filter_to_columns(clean, self.OLTP, self.TABLE)
        if not clean:
            raise ValidationError("None of the fields exist in the employees table.")

        with self.transaction() as conn:
            before = self.fetch_one(f"SELECT * FROM {self.OLTP}.{self.TABLE} WHERE employee_id = :i FOR UPDATE",
                                    {"i": employee_id}, conn)
            if not before:
                raise RecordNotFoundError(f"Employee id {employee_id} not found.")
            diff = {k: (before.get(k), val) for k, val in clean.items() if not self._same(before.get(k), val)}
            if not diff:
                return {}
            new_values = {k: new for k, (_, new) in diff.items()}
            if "first_name" in new_values or "last_name" in new_values:
                first = new_values.get("first_name", before.get("first_name")) or ""
                last = new_values.get("last_name", before.get("last_name")) or ""
                new_values["employee_name"] = f"{first} {last}".strip()
            sets = ", ".join(f"`{k}` = :{k}" for k in new_values)
            try:
                self.execute(f"UPDATE {self.OLTP}.{self.TABLE} SET {sets} WHERE employee_id = :_id",
                             {**new_values, "_id": employee_id}, conn)
            except IntegrityViolationError as exc:
                raise ValidationError(f"Update rejected by the database (duplicate or invalid reference): {exc}") from exc
        self._log.info("Updated employee_id=%s fields=%s", employee_id, ", ".join(diff))
        return diff

    def set_status(self, employee_id: int, status: str) -> Dict[str, Tuple[Any, Any]]:
        """Soft-delete: Active / Inactive / Terminated."""
        return self.update(employee_id, {"employment_status": status})

    # ------------------------------------------------------------------ #
    # Delete
    # ------------------------------------------------------------------ #
    def delete(self, employee_id: int) -> None:
        """Hard delete. Refused when the employee has reviews or assignments (use ``set_status``)."""
        with self.transaction() as conn:
            refs = self.fetch_one(
                f"SELECT (SELECT COUNT(*) FROM {self.OLTP}.performance_reviews WHERE employee_id = :i) AS reviews, "
                f"(SELECT COUNT(*) FROM {self.OLTP}.assignments WHERE employee_id = :i) AS assignments",
                {"i": employee_id}, conn) or {}
            if refs.get("reviews") or refs.get("assignments"):
                raise DatabaseError("Employee has reviews or assignments - set the status to Terminated instead.")
            if not self.execute(f"DELETE FROM {self.OLTP}.{self.TABLE} WHERE employee_id = :i",
                                {"i": employee_id}, conn):
                raise RecordNotFoundError(f"Employee id {employee_id} not found.")
