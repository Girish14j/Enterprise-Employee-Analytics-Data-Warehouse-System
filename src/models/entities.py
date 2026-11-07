"""Domain entities: Employee, Project, Review.

Attribute names match the ``hr_oltp`` column names exactly, so ``to_db_row()``
can be handed straight to the managers.  Every attribute is validated on
assignment (see ``Field``), and behaviour lives on the entity itself.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, Mapping, Optional

from src.exceptions import ValidationError
from src.models import validators as v
from src.models.base import Entity, Field

EMPLOYMENT_STATUSES = ("Active", "Inactive", "Terminated")
YES_NO = ("Yes", "No")


# --------------------------------------------------------------------------- #
# Employee
# --------------------------------------------------------------------------- #
class Employee(Entity):
    """Row of ``hr_oltp.employees``."""

    employee_id = Field(v.int_range(1, 2**63 - 1))
    employee_number = Field(v.int_range(1, 999_999_999), required=True)
    first_name = Field(v.text(100), required=True)
    last_name = Field(v.text(100), required=True)
    email = Field(v.email(), required=True)
    department_id = Field(v.int_range(1, 2**31 - 1), required=True)
    job_role_id = Field(v.int_range(1, 2**31 - 1), required=True)
    job_level = Field(v.int_range(1, 5))
    monthly_income = Field(v.number_range(1, 10_000_000))
    hire_date = Field(v.date_value())
    age = Field(v.int_range(18, 70))
    gender = Field(v.text(30))
    marital_status = Field(v.text(30))
    education_field = Field(v.text(60))
    business_travel = Field(v.text(40))
    overtime = Field(v.choice(YES_NO))
    attrition = Field(v.choice(YES_NO))
    employment_status = Field(v.choice(EMPLOYMENT_STATUSES))
    manager_id = Field(v.int_range(1, 2**63 - 1))

    # -- derived ------------------------------------------------------------ #
    @property
    def full_name(self) -> str:
        return f"{self.first_name or ''} {self.last_name or ''}".strip()

    @property
    def is_active(self) -> bool:
        return (self.employment_status or "Active") == "Active"

    # -- behaviour ---------------------------------------------------------- #
    def validate(self) -> "Employee":
        super().validate()
        if self.hire_date and self.hire_date > date.today():
            raise ValidationError("Hire date cannot be in the future.")
        return self

    def change_department(self, department_id: int) -> "Employee":
        self.department_id = department_id
        return self

    def promote(self, levels: int = 1) -> "Employee":
        """Raise the job level (max 5)."""
        self.job_level = min((self.job_level or 1) + levels, 5)
        return self

    def give_raise(self, percent: float) -> "Employee":
        if not self.monthly_income:
            raise ValidationError("Cannot apply a raise: monthly income is not set.")
        if percent <= 0 or percent > 100:
            raise ValidationError("Raise must be between 0 and 100 percent.")
        self.monthly_income = round(self.monthly_income * (1 + percent / 100), 2)
        return self

    def to_db_row(self) -> Dict[str, Any]:
        """Column -> value dict for INSERT (``employee_id`` excluded, NULLs omitted)."""
        row = {k: val for k, val in self.to_dict().items() if val is not None and k != "employee_id"}
        row["employee_name"] = self.full_name
        return row

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> "Employee":
        emp = super().from_row(row)  # type: ignore[assignment]
        if not emp.first_name and row.get("employee_name"):
            parts = str(row["employee_name"]).split(" ", 1)
            emp._first_name = parts[0]
            emp._last_name = parts[1] if len(parts) > 1 else ""
        return emp


# --------------------------------------------------------------------------- #
# Project
# --------------------------------------------------------------------------- #
class Project(Entity):
    """Row of ``hr_oltp.projects``."""

    ACTIVE_STATUSES = ("planned", "active", "in progress", "on hold")

    project_id = Field(v.int_range(1, 2**31 - 1))
    project_name = Field(v.text(150), required=True)
    department_id = Field(v.int_range(1, 2**31 - 1), required=True)
    start_date = Field(v.date_value(), required=True)
    end_date = Field(v.date_value())
    project_status = Field(v.text(30), required=True)
    budget = Field(v.number_range(0, 10**13))

    @property
    def duration_days(self) -> Optional[int]:
        if self.start_date and self.end_date:
            return (self.end_date - self.start_date).days
        return None

    @property
    def is_closed(self) -> bool:
        return (self.project_status or "").lower() in ("completed", "closed", "cancelled")

    def is_overdue(self, today: Optional[date] = None) -> bool:
        today = today or date.today()
        return bool(self.end_date and self.end_date < today and not self.is_closed)

    def validate(self) -> "Project":
        super().validate()
        if self.end_date and self.start_date and self.end_date < self.start_date:
            raise ValidationError("End date cannot be before the start date.")
        return self

    def close(self, end_date: Optional[date] = None) -> "Project":
        self.end_date = end_date or date.today()
        self.project_status = "Completed"
        return self

    def to_db_row(self) -> Dict[str, Any]:
        return {k: val for k, val in self.to_dict().items() if val is not None and k != "project_id"}


# --------------------------------------------------------------------------- #
# Review
# --------------------------------------------------------------------------- #
class Review(Entity):
    """Row of ``hr_oltp.performance_reviews``.

    The DDL does not constrain rating / satisfaction, so the scale is enforced
    here.  IBM HR data uses 1-4.  Change ``SCALE`` if your synthetic data differs.
    """

    SCALE = (1, 4)
    RATING_LABELS = {1: "Low", 2: "Good", 3: "Excellent", 4: "Outstanding"}

    review_id = Field(v.int_range(1, 2**31 - 1))
    employee_id = Field(v.int_range(1, 2**63 - 1), required=True)
    project_id = Field(v.int_range(1, 2**31 - 1), required=True)
    review_date = Field(v.date_value(), required=True)
    performance_rating = Field(v.int_range(*SCALE))
    job_satisfaction = Field(v.int_range(*SCALE))
    review_score = Field(v.number_range(0, 100))

    @property
    def review_year(self) -> Optional[int]:
        return self.review_date.year if self.review_date else None

    @property
    def rating_label(self) -> str:
        return self.RATING_LABELS.get(self.performance_rating or 0, "Not rated")

    def is_high_performer(self, threshold: float = 80.0) -> bool:
        return (self.review_score or 0) >= threshold

    def validate(self) -> "Review":
        super().validate()
        if self.review_date and self.review_date > date.today():
            raise ValidationError("Review date cannot be in the future.")
        if self.performance_rating is None and self.review_score is None:
            raise ValidationError("Enter a performance rating or a review score.")
        return self

    def to_db_row(self) -> Dict[str, Any]:
        row = {k: val for k, val in self.to_dict().items() if val is not None and k != "review_id"}
        row["review_year"] = self.review_year
        return row
