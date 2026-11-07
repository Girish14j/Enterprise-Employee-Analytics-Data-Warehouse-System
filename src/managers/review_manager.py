"""CRUD for ``hr_oltp.performance_reviews``."""
from __future__ import annotations

from typing import Optional

import pandas as pd

from src.exceptions import DuplicateRecordError, IntegrityViolationError, RecordNotFoundError, ValidationError
from src.managers.base_manager import BaseManager
from src.models.entities import Review


class ReviewManager(BaseManager):
    TABLE = "performance_reviews"

    def create(self, review: Review) -> int:
        """Insert a review. ``review_id`` is not AUTO_INCREMENT, so the next id is allocated here."""
        review.validate()
        row = self._filter_to_columns(review.to_db_row(), self.OLTP, self.TABLE)
        names = ["review_id", *row]
        try:
            with self.transaction() as conn:
                if not self.fetch_one(f"SELECT 1 FROM {self.OLTP}.employees WHERE employee_id = :i",
                                      {"i": review.employee_id}, conn):
                    raise RecordNotFoundError(f"Employee id {review.employee_id} not found.")
                if not self.fetch_one(f"SELECT 1 FROM {self.OLTP}.projects WHERE project_id = :i",
                                      {"i": review.project_id}, conn):
                    raise RecordNotFoundError(f"Project {review.project_id} not found.")
                if self.fetch_one(
                        f"SELECT 1 FROM {self.OLTP}.{self.TABLE} WHERE employee_id = :e AND project_id = :p "
                        "AND review_date = :d", {"e": review.employee_id, "p": review.project_id,
                                                 "d": review.review_date}, conn):
                    raise DuplicateRecordError("A review for this employee, project and date already exists.")
                new_id = self._next_id(self.TABLE, "review_id", conn)
                self.execute(
                    f"INSERT INTO {self.OLTP}.{self.TABLE} ({self._col_list(names)}) "
                    f"VALUES ({', '.join(':' + n for n in names)})", {"review_id": new_id, **row}, conn)
        except IntegrityViolationError as exc:
            raise ValidationError(f"Review rejected by the database: {exc}") from exc
        self._log.info("Created review_id=%s", new_id)
        return new_id

    def get(self, review_id: int) -> Review:
        row = self.fetch_one(f"SELECT * FROM {self.OLTP}.{self.TABLE} WHERE review_id = :i", {"i": review_id})
        if not row:
            raise RecordNotFoundError(f"Review {review_id} not found.")
        return Review.from_row(row)

    def list_recent(self, limit: int = 25, employee_id: Optional[int] = None) -> pd.DataFrame:
        return self.fetch_df(
            f"SELECT r.review_id, e.employee_number, e.employee_name, p.project_name, r.review_date, "
            f"r.performance_rating, r.job_satisfaction, r.review_score "
            f"FROM {self.OLTP}.{self.TABLE} r JOIN {self.OLTP}.employees e ON e.employee_id = r.employee_id "
            f"JOIN {self.OLTP}.projects p ON p.project_id = r.project_id "
            "WHERE (:emp IS NULL OR r.employee_id = :emp) "
            f"ORDER BY r.review_date DESC, r.review_id DESC LIMIT {max(1, min(int(limit), 500))}",
            {"emp": employee_id})
