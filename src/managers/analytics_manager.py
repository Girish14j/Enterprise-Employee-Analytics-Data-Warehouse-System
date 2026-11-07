"""Read-only analytics over the ``hr_dw`` star schema.

Every query is a CTE and/or window-function query, as required by the brief:
``LAG`` (year-over-year), ``DENSE_RANK`` (top performers), ``ROW_NUMBER`` + ``LAG``
(attrition risk), ``NTILE`` (project bottlenecks).
"""
from __future__ import annotations

from typing import Any, Dict, Optional

import pandas as pd

from src.managers.base_manager import BaseManager

_CLOSED = "('completed','closed','cancelled')"
_F = "hr_dw.fact_performance_reviews"
_E = "hr_dw.dim_employee"
_D = "hr_dw.dim_department"
_P = "hr_dw.dim_project"
_T = "hr_dw.dim_date"


class AnalyticsManager(BaseManager):
    # ------------------------------------------------------------------ #
    # Filters / KPIs
    # ------------------------------------------------------------------ #
    def departments(self) -> pd.DataFrame:
        return self.fetch_df(f"SELECT department_sk, department_name FROM {_D} ORDER BY department_name")

    def years(self) -> list:
        rows = self.fetch_all(f"SELECT DISTINCT t.year_number AS y FROM {_F} f "
                              f"JOIN {_T} t ON t.date_sk = f.review_date_sk ORDER BY y DESC")
        return [int(r["y"]) for r in rows]

    def kpis(self) -> Dict[str, Any]:
        return self.fetch_one(
            f"SELECT (SELECT COUNT(*) FROM {_F}) AS total_reviews, "
            f"(SELECT COUNT(DISTINCT employee_number) FROM {_E} WHERE is_current = 1) AS current_employees, "
            f"(SELECT COUNT(*) FROM {_E}) AS employee_versions, "
            f"(SELECT ROUND(AVG(review_score), 2) FROM {_F}) AS avg_score, "
            f"(SELECT ROUND(AVG(performance_rating), 2) FROM {_F}) AS avg_rating") or {}

    # ------------------------------------------------------------------ #
    # Year-over-year performance (LAG)
    # ------------------------------------------------------------------ #
    def yoy_performance(self, department_sk: Optional[int] = None) -> pd.DataFrame:
        return self.fetch_df(
            f"""
            WITH yearly AS (
                SELECT t.year_number AS review_year,
                       COUNT(*)                              AS reviews,
                       ROUND(AVG(f.review_score), 2)         AS avg_score,
                       ROUND(AVG(f.performance_rating), 3)   AS avg_rating,
                       ROUND(AVG(f.job_satisfaction), 3)     AS avg_satisfaction
                FROM {_F} f
                JOIN {_T} t ON t.date_sk = f.review_date_sk
                WHERE (:dept IS NULL OR f.department_sk = :dept)
                GROUP BY t.year_number
            )
            SELECT y.*,
                   ROUND(y.avg_score - LAG(y.avg_score) OVER (ORDER BY y.review_year), 2) AS score_change,
                   ROUND(100 * (y.avg_score / NULLIF(LAG(y.avg_score) OVER (ORDER BY y.review_year), 0) - 1), 2)
                       AS score_change_pct
            FROM yearly y
            ORDER BY y.review_year
            """, {"dept": department_sk})

    def yoy_by_department(self) -> pd.DataFrame:
        return self.fetch_df(
            f"""
            SELECT t.year_number AS review_year, d.department_name,
                   COUNT(*) AS reviews, ROUND(AVG(f.review_score), 2) AS avg_score,
                   ROUND(AVG(f.performance_rating), 3) AS avg_rating
            FROM {_F} f
            JOIN {_T} t ON t.date_sk = f.review_date_sk
            JOIN {_D} d ON d.department_sk = f.department_sk
            GROUP BY t.year_number, d.department_name
            ORDER BY t.year_number, d.department_name
            """)

    # ------------------------------------------------------------------ #
    # Top performers per department (DENSE_RANK)
    # ------------------------------------------------------------------ #
    def top_performers(self, year: Optional[int] = None, top_n: int = 5,
                       department_sk: Optional[int] = None, min_reviews: int = 1) -> pd.DataFrame:
        return self.fetch_df(
            f"""
            WITH employee_scores AS (
                SELECT f.department_sk,
                       de.employee_number,
                       MAX(de.employee_name)               AS employee_name,
                       ROUND(AVG(f.review_score), 2)       AS avg_score,
                       ROUND(AVG(f.performance_rating), 2) AS avg_rating,
                       COUNT(*)                            AS review_count
                FROM {_F} f
                JOIN {_E} de ON de.employee_sk = f.employee_sk
                JOIN {_T} t  ON t.date_sk = f.review_date_sk
                WHERE f.review_score IS NOT NULL
                  AND (:year IS NULL OR t.year_number = :year)
                  AND (:dept IS NULL OR f.department_sk = :dept)
                GROUP BY f.department_sk, de.employee_number
                HAVING COUNT(*) >= :min_reviews
            ),
            ranked AS (
                SELECT es.*,
                       DENSE_RANK() OVER (PARTITION BY es.department_sk
                                          ORDER BY es.avg_score DESC) AS dept_rank
                FROM employee_scores es
            )
            SELECT d.department_name, r.dept_rank, r.employee_number, r.employee_name,
                   r.avg_score, r.avg_rating, r.review_count
            FROM ranked r
            JOIN {_D} d ON d.department_sk = r.department_sk
            WHERE r.dept_rank <= :top_n
            ORDER BY d.department_name, r.dept_rank, r.employee_name
            """, {"year": year, "dept": department_sk, "top_n": int(top_n), "min_reviews": int(min_reviews)})

    # ------------------------------------------------------------------ #
    # Attrition
    # ------------------------------------------------------------------ #
    @property
    def attrition_available(self) -> bool:
        return self.has_column(self.DW, "dim_employee", "attrition")

    def attrition_by(self, group: str = "department") -> pd.DataFrame:
        """Attrition rate of the CURRENT employee versions by department or job role."""
        if not self.attrition_available:
            return pd.DataFrame(columns=["grp", "headcount", "leavers", "attrition_rate"])
        expr = "de.job_role" if group == "job_role" else "d.department_name"
        df = self.fetch_df(
            f"""
            SELECT {expr} AS grp,
                   COUNT(*) AS headcount,
                   SUM(CASE WHEN UPPER(CAST(de.attrition AS CHAR)) IN ('YES','Y','1','TRUE')
                            THEN 1 ELSE 0 END) AS leavers
            FROM {_E} de
            JOIN {_D} d ON d.department_sk = de.department_sk
            WHERE de.is_current = 1
            GROUP BY {expr}
            ORDER BY leavers DESC
            """)
        df["attrition_rate"] = (100 * df["leavers"] / df["headcount"]).round(1)
        return df

    def _risk_cte(self) -> str:
        """CTE chain: one scored row per CURRENT employee who has not left and has a review."""
        leaver = ("AND UPPER(CAST(de.attrition AS CHAR)) NOT IN ('YES','Y','1','TRUE')"
                  if self.attrition_available else "")
        return f"""
            WITH review_seq AS (
                SELECT de.employee_number, f.review_score, f.job_satisfaction, f.performance_rating,
                       ROW_NUMBER() OVER (PARTITION BY de.employee_number
                                          ORDER BY f.review_date_sk DESC, f.fact_review_sk DESC) AS rn,
                       LAG(f.review_score) OVER (PARTITION BY de.employee_number
                                          ORDER BY f.review_date_sk, f.fact_review_sk) AS prev_score
                FROM {_F} f JOIN {_E} de ON de.employee_sk = f.employee_sk
            ),
            latest AS (SELECT * FROM review_seq WHERE rn = 1),
            current_emp AS (
                SELECT de.employee_number, de.employee_name, de.department_sk, de.job_role, de.monthly_income,
                       AVG(de.monthly_income) OVER (PARTITION BY de.department_sk) AS dept_avg_income
                FROM {_E} de WHERE de.is_current = 1 {leaver}
            ),
            dept_score AS (
                SELECT department_sk, AVG(review_score) AS dept_avg_score FROM {_F} GROUP BY department_sk
            ),
            scored AS (
                SELECT ce.employee_number, ce.employee_name, ce.department_sk, d.department_name, ce.job_role,
                       l.review_score AS last_score, l.prev_score, l.job_satisfaction AS last_satisfaction,
                       ce.monthly_income,
                       (CASE WHEN l.job_satisfaction <= 2 THEN 40 ELSE 0 END
                      + CASE WHEN l.prev_score IS NOT NULL AND l.review_score IS NOT NULL
                                  AND l.prev_score - l.review_score >= 10 THEN 20 ELSE 0 END
                      + CASE WHEN l.review_score < ds.dept_avg_score THEN 20 ELSE 0 END
                      + CASE WHEN ce.monthly_income < 0.8 * ce.dept_avg_income THEN 20 ELSE 0 END) AS risk_score
                FROM current_emp ce
                JOIN latest l      ON l.employee_number = ce.employee_number
                JOIN {_D} d        ON d.department_sk = ce.department_sk
                JOIN dept_score ds ON ds.department_sk = ce.department_sk
            ),
            banded AS (
                SELECT s.*, CASE WHEN s.risk_score <= 20 THEN 'Low'
                                 WHEN s.risk_score <= 40 THEN 'Medium' ELSE 'High' END AS risk_band
                FROM scored s
            )
        """

    def attrition_risk(self, limit: int = 50, department_sk: Optional[int] = None) -> pd.DataFrame:
        """Highest-risk current employees (rule-based score 0-100 from the latest review)."""
        return self.fetch_df(
            self._risk_cte() + f"""
            SELECT * FROM banded
            WHERE (:dept IS NULL OR department_sk = :dept)
            ORDER BY risk_score DESC, last_satisfaction ASC, last_score ASC
            LIMIT {max(1, min(int(limit), 1000))}
            """, {"dept": department_sk})

    def attrition_risk_summary(self) -> pd.DataFrame:
        """Employee counts for the WHOLE population by department, risk score and band."""
        return self.fetch_df(
            self._risk_cte() + """
            SELECT department_name, risk_score, risk_band, COUNT(*) AS employees
            FROM banded
            GROUP BY department_name, risk_score, risk_band
            ORDER BY department_name, risk_score
            """)

    # ------------------------------------------------------------------ #
    # Project bottlenecks (NTILE)
    # ------------------------------------------------------------------ #
    def project_bottlenecks(self) -> pd.DataFrame:
        return self.fetch_df(
            f"""
            WITH project_stats AS (
                SELECT p.project_sk, p.project_id, p.project_name, d.department_name, p.project_status,
                       p.start_date, p.end_date, p.budget,
                       COUNT(f.fact_review_sk)             AS review_count,
                       COUNT(DISTINCT de.employee_number)  AS reviewed_employees,
                       ROUND(AVG(f.review_score), 2)       AS avg_score,
                       ROUND(AVG(f.job_satisfaction), 2)   AS avg_satisfaction,
                       CASE WHEN p.end_date IS NOT NULL AND p.end_date < CURDATE()
                                 AND LOWER(p.project_status) NOT IN {_CLOSED} THEN 1 ELSE 0 END AS is_overdue
                FROM {_P} p
                JOIN {_D} d ON d.department_sk = p.department_sk
                LEFT JOIN {_F} f ON f.project_sk = p.project_sk
                LEFT JOIN {_E} de ON de.employee_sk = f.employee_sk
                GROUP BY p.project_sk, p.project_id, p.project_name, d.department_name, p.project_status,
                         p.start_date, p.end_date, p.budget
            ),
            ranked AS (
                SELECT ps.*,
                       CASE WHEN ps.avg_score IS NULL THEN NULL
                            ELSE NTILE(4) OVER (PARTITION BY (ps.avg_score IS NULL) ORDER BY ps.avg_score)
                       END AS score_quartile
                FROM project_stats ps
            )
            SELECT r.*,
                   CASE WHEN r.is_overdue = 1 THEN 'Overdue'
                        WHEN LOWER(r.project_status) IN {_CLOSED} THEN 'Completed'
                        WHEN r.score_quartile = 1 THEN 'Low performance'
                        ELSE 'On track' END AS bottleneck_flag
            FROM ranked r
            ORDER BY r.is_overdue DESC, r.avg_score ASC
            """)

    # ------------------------------------------------------------------ #
    # SCD2 history
    # ------------------------------------------------------------------ #
    def employee_history(self, employee_number: int) -> pd.DataFrame:
        return self.fetch_df(
            f"""
            SELECT de.employee_sk, de.employee_number, de.employee_name, d.department_name, de.job_role,
                   de.job_level, de.monthly_income, de.start_date, de.end_date, de.is_current, de.change_reason
            FROM {_E} de JOIN {_D} d ON d.department_sk = de.department_sk
            WHERE de.employee_number = :n
            ORDER BY de.start_date, de.employee_sk
            """, {"n": employee_number})

    def changes_by_year(self) -> pd.DataFrame:
        """How many SCD2 versions started each year, grouped by the recorded reason."""
        return self.fetch_df(
            f"""
            SELECT YEAR(start_date) AS change_year, COALESCE(change_reason, 'Initial / unspecified') AS reason,
                   COUNT(*) AS versions
            FROM {_E}
            GROUP BY YEAR(start_date), COALESCE(change_reason, 'Initial / unspecified')
            ORDER BY change_year, reason
            """)