"""Use-case layer used by the Streamlit pages.

Every write follows the same two steps:

    1. save to OLTP (``hr_oltp``) in its own transaction         <- the user's data is safe
    2. run the matching ETL step so the warehouse (``hr_dw``) is updated

If step 2 fails, the OLTP change stays saved, the result carries ``sync_error`` and the
user can retry from the *Warehouse sync* page.  Nothing is lost and nothing is half-written.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from src.etl.pipeline import ETLPipeline, SyncReport
from src.exceptions import AppError
from src.managers.analytics_manager import AnalyticsManager
from src.managers.employee_manager import EmployeeManager
from src.managers.project_manager import ProjectManager
from src.managers.review_manager import ReviewManager
from src.models.entities import Employee, Project, Review

logger = logging.getLogger(__name__)


@dataclass
class ActionResult:
    """Outcome of a service call."""

    record_id: int
    message: str
    changes: Dict[str, Tuple[Any, Any]] = field(default_factory=dict)
    sync: List[SyncReport] = field(default_factory=list)
    sync_error: Optional[str] = None

    @property
    def synced(self) -> bool:
        return self.sync_error is None and bool(self.sync)

    @property
    def new_versions(self) -> int:
        """SCD2 versions created by this action."""
        return sum(r.inserted for r in self.sync if "SCD2" in r.step)


class HRService:
    def __init__(self) -> None:
        self.employees = EmployeeManager()
        self.projects = ProjectManager()
        self.reviews = ReviewManager()
        self.analytics = AnalyticsManager()
        self.etl = ETLPipeline()

    # ------------------------------------------------------------------ #
    def _sync(self, result: ActionResult, runner, *args: Any) -> ActionResult:
        try:
            result.sync = runner(*args)
        except AppError as exc:
            logger.error("Warehouse sync failed after OLTP save: %s", exc)
            result.sync_error = str(exc)
        return result

    # ------------------------------------------------------------------ #
    # Employees
    # ------------------------------------------------------------------ #
    def onboard_employee(self, employee: Employee, auto_sync: bool = True) -> ActionResult:
        employee_id = self.employees.create(employee)
        result = ActionResult(employee_id, f"Employee {employee.full_name} saved (id {employee_id}).")
        return self._sync(result, self.etl.sync_employee, employee.employee_number) if auto_sync else result

    def update_employee(self, employee_id: int, changes: Dict[str, Any], auto_sync: bool = True) -> ActionResult:
        """Update an employee. A change to department / role / level / income creates an SCD2 version."""
        diff = self.employees.update(employee_id, changes)
        result = ActionResult(employee_id, "No changes to save." if not diff else "Employee updated.", changes=diff)
        if not diff or not auto_sync:
            return result
        number = self.employees.get_detail(employee_id)["employee_number"]
        return self._sync(result, self.etl.sync_employee, int(number))

    # ------------------------------------------------------------------ #
    # Projects
    # ------------------------------------------------------------------ #
    def create_project(self, project: Project, auto_sync: bool = True) -> ActionResult:
        project_id = self.projects.create(project)
        result = ActionResult(project_id, f"Project '{project.project_name}' saved (id {project_id}).")
        return self._sync(result, self.etl.sync_project, project_id) if auto_sync else result

    def assign_employee(self, employee_id: int, project_id: int, allocation_pct: float,
                        is_primary: bool) -> ActionResult:
        assignment_id = self.projects.assign_employee(employee_id, project_id, allocation_pct, is_primary)
        return ActionResult(assignment_id, "Employee assigned to the project.")

    # ------------------------------------------------------------------ #
    # Reviews
    # ------------------------------------------------------------------ #
    def submit_review(self, review: Review, auto_sync: bool = True) -> ActionResult:
        review_id = self.reviews.create(review)
        result = ActionResult(review_id, f"Review saved (id {review_id}).")
        return self._sync(result, self.etl.sync_review, review_id) if auto_sync else result
