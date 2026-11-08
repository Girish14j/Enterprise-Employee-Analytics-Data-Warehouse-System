"""
Bulk ETL: hr_oltp -> hr_dw.

This runner deliberately does NOT read from hr_staging, import CSV files,
generate data, drop tables, truncate tables, or recreate the warehouse.
It invokes the repository's existing ETLPipeline, which performs:
  1. departments -> dim_department
  2. projects -> dim_project
  3. performance review dates -> dim_date
  4. employees -> dim_employee (SCD Type 2)
  5. performance_reviews -> fact_performance_reviews

Run from the repository root:
    python run_oltp_to_olap.py
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure imports work when this file is run from the repository root.
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def main() -> int:
    try:
        from src.etl.pipeline import ETLPipeline
        from src.database.db_manager import DatabaseConnection

        pipeline = ETLPipeline()

        print("=" * 68)
        print("BULK ETL: hr_oltp  ->  hr_dw")
        print("=" * 68)
        print("Source: hr_oltp")
        print("Target: hr_dw")
        print("Staging database and CSV files: NOT USED")
        print()

        # Preview counts before changing the warehouse.
        print("Checking pending changes...")
        pending = pipeline.pending_changes()
        for key, value in pending.items():
            print(f"  {key}: {value:,}")
        print()

        print("Starting full warehouse sync...")
        reports = pipeline.run_full_sync()

        print()
        print("ETL step results")
        print("-" * 68)
        print(f"{'Step':<34} {'Inserted':>10} {'Updated':>10} {'Closed':>9} {'Skipped':>9}")
        print("-" * 68)
        for report in reports:
            print(
                f"{report.step:<34} "
                f"{report.inserted:>10,} "
                f"{report.updated:>10,} "
                f"{report.closed:>9,} "
                f"{report.skipped:>9,}"
            )
            for note in report.notes:
                print(f"    Note: {note}")

        print()
        print("Running SCD Type 2 and fact validation...")
        checks = pipeline.validate_scd2()
        for name, count in checks.items():
            status = "PASS" if count == 0 else "CHECK"
            print(f"  [{status}] {name}: {count:,}")

        print()
        with pipeline.connection() as conn:
            from sqlalchemy import text
            tables = (
                "dim_department",
                "dim_project",
                "dim_date",
                "dim_employee",
                "fact_performance_reviews",
            )
            print("Final warehouse row counts")
            print("-" * 40)
            for table in tables:
                count = conn.execute(
                    text(f"SELECT COUNT(*) FROM hr_dw.{table}")
                ).scalar_one()
                print(f"  hr_dw.{table}: {count:,}")

        print()
        if any(checks.values()):
            print("ETL completed, but one or more validation checks need attention.")
            return 2

        print("ETL completed and all validation checks returned zero.")
        return 0

    except Exception as exc:
        print()
        print("ETL FAILED.")
        print(f"{type(exc).__name__}: {exc}")
        print(
            "\nNo staging import was attempted. Check that your .env file and "
            "Aiven CA certificate are configured, both databases are accessible, "
            "the OLTP tables contain data, and the uploaded OLAP schema is already "
            "created in hr_dw."
        )
        return 1

    finally:
        # Close the shared SQLAlchemy pool cleanly after this CLI run.
        try:
            from src.database.db_manager import DatabaseConnection
            DatabaseConnection.dispose()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
