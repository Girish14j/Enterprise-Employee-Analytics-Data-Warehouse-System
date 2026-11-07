"""CRUD for ``hr_oltp.projects`` and ``hr_oltp.assignments``."""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

import pandas as pd

from src.exceptions import (DuplicateRecordError, IntegrityViolationError, RecordNotFoundError,
                            ValidationError)
from src.managers.base_manager import BaseManager
from src.models.entities import Project

DEFAULT_STATUSES = ["Planned", "Active", "On Hold", "Completed", "Cancelled"]


class ProjectManager(BaseManager):
    TABLE = "projects"

    def status_options(self) -> List[str]:
        """Statuses already used in the data, plus sensible defaults."""
        rows = self.fetch_all(f"SELECT DISTINCT project_status AS s FROM {self.OLTP}.{self.TABLE} ORDER BY 1")
        existing = [r["s"] for r in rows if r["s"]]
        return existing + [s for s in DEFAULT_STATUSES if s.lower() not in {e.lower() for e in existing}]

    # -- projects ----------------------------------------------------------- #
    def create(self, project: Project) -> int:
        """Insert a project. ``project_id`` is not AUTO_INCREMENT, so the next id is allocated here."""
        project.validate()
        row = self._filter_to_columns(project.to_db_row(), self.OLTP, self.TABLE)
        cols = self._col_list(["project_id", *row])
        marks = ", ".join(f":{k}" for k in ["project_id", *row])
        try:
            with self.transaction() as conn:
                new_id = self._next_id(self.TABLE, "project_id", conn)
                self.execute(f"INSERT INTO {self.OLTP}.{self.TABLE} ({cols}) VALUES ({marks})",
                             {"project_id": new_id, **row}, conn)
        except IntegrityViolationError as exc:
            raise ValidationError(f"Could not save the project - check the department exists "
                                  f"and the dates/budget are valid. ({exc})") from exc
        self._log.info("Created project_id=%s", new_id)
        return new_id

    def get(self, project_id: int) -> Project:
        row = self.fetch_one(f"SELECT * FROM {self.OLTP}.{self.TABLE} WHERE project_id = :i", {"i": project_id})
        if not row:
            raise RecordNotFoundError(f"Project {project_id} not found.")
        return Project.from_row(row)

    def list_projects(self, department_id: Optional[int] = None, status: Optional[str] = None,
                      limit: int = 500) -> pd.DataFrame:
        return self.fetch_df(
            f"SELECT p.project_id, p.project_name, d.department_name, p.project_status, p.start_date, "
            f"p.end_date, p.budget, COUNT(a.assignment_id) AS team_size "
            f"FROM {self.OLTP}.{self.TABLE} p JOIN {self.OLTP}.departments d ON d.department_id = p.department_id "
            f"LEFT JOIN {self.OLTP}.assignments a ON a.project_id = p.project_id "
            "WHERE (:dept IS NULL OR p.department_id = :dept) AND (:status IS NULL OR p.project_status = :status) "
            "GROUP BY p.project_id, p.project_name, d.department_name, p.project_status, p.start_date, "
            "p.end_date, p.budget "
            f"ORDER BY p.project_id DESC LIMIT {max(1, min(int(limit), 2000))}",
            {"dept": department_id, "status": status})

    def update_status(self, project_id: int, status: str, end_date: Optional[date] = None) -> None:
        project = self.get(project_id)
        project.project_status = status
        if end_date:
            project.end_date = end_date
        project.validate()
        self.execute(f"UPDATE {self.OLTP}.{self.TABLE} SET project_status = :s, end_date = :e "
                     "WHERE project_id = :i", {"s": project.project_status, "e": project.end_date, "i": project_id})

    # -- assignments -------------------------------------------------------- #
    def assign_employee(self, employee_id: int, project_id: int, allocation_pct: float = 100.0,
                        is_primary: bool = False, assigned_date: Optional[date] = None) -> int:
        """Link an employee to a project. Returns the new ``assignment_id``."""
        if not (0 < float(allocation_pct) <= 100):
            raise ValidationError("Allocation must be greater than 0 and at most 100.")
        try:
            with self.transaction() as conn:
                if not self.fetch_one(f"SELECT 1 FROM {self.OLTP}.employees WHERE employee_id = :i",
                                      {"i": employee_id}, conn):
                    raise RecordNotFoundError(f"Employee id {employee_id} not found.")
                if not self.fetch_one(f"SELECT 1 FROM {self.OLTP}.{self.TABLE} WHERE project_id = :i",
                                      {"i": project_id}, conn):
                    raise RecordNotFoundError(f"Project {project_id} not found.")
                if self.fetch_one(f"SELECT 1 FROM {self.OLTP}.assignments WHERE employee_id = :e AND project_id = :p",
                                  {"e": employee_id, "p": project_id}, conn):
                    raise DuplicateRecordError("This employee is already assigned to the project.")
                new_id = self._next_id("assignments", "assignment_id", conn)
                self.execute(
                    f"INSERT INTO {self.OLTP}.assignments (assignment_id, employee_id, project_id, is_primary, "
                    "assigned_date, allocation_pct) VALUES (:a, :e, :p, :pri, :d, :alloc)",
                    {"a": new_id, "e": employee_id, "p": project_id, "pri": bool(is_primary),
                     "d": assigned_date or date.today(), "alloc": float(allocation_pct)}, conn)
        except IntegrityViolationError as exc:
            raise ValidationError(f"Assignment rejected by the database: {exc}") from exc
        return new_id

    def list_assignments(self, project_id: int) -> pd.DataFrame:
        return self.fetch_df(
            f"SELECT a.assignment_id, e.employee_number, e.employee_name, jr.job_title, a.allocation_pct, "
            f"a.is_primary, a.assigned_date FROM {self.OLTP}.assignments a "
            f"JOIN {self.OLTP}.employees e ON e.employee_id = a.employee_id "
            f"JOIN {self.OLTP}.job_roles jr ON jr.job_role_id = e.job_role_id "
            "WHERE a.project_id = :p ORDER BY a.is_primary DESC, e.employee_name", {"p": project_id})
