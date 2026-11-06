"""
Employee Analytics & Data Warehouse - Phase 1 Data Synthesizer (corrected)

What this script does:
1. Reads the IBM HR Analytics CSV supplied for the assignment.
2. Samples rows with replacement to create 100,000+ synthetic employees.
3. Uses Faker for unique-looking names, emails and SCD2 change dates.
4. Creates SCD Type 2 history (promotion / department transfer / salary bump)
   for a configurable subset of employees, with role-department consistency.
5. Creates synthetic projects, project assignments and annual performance
   reviews (needed for Dim_Project and Fact_PerformanceReviews).
6. Validates SCD2 integrity, saves CSVs and optionally loads MySQL staging.

All generated data is synthetic and must not be represented as real.
"""

from __future__ import annotations

import argparse
import os
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from faker import Faker
from dotenv import load_dotenv

IGNORED_CONSTANT_COLUMNS = ["EmployeeCount", "Over18", "StandardHours"]
OPEN_END_DATE = date(2099, 12, 31)
CHANGE_TYPES = ["promotion", "transfer", "salary_bump"]
CHANGE_PROBS = [0.40, 0.20, 0.40]


def parse_args():
    p = argparse.ArgumentParser(
        description="Generate 100,000+ synthetic IBM HR records, SCD2 history, "
        "projects, assignments and reviews."
    )
    p.add_argument("--input", default="WA_Fn-UseC_-HR-Employee-Attrition.csv")
    p.add_argument("--target-rows", type=int, default=100_000,
                   help="Synthetic current employees (minimum 100000).")
    p.add_argument("--historical-pct", type=float, default=0.20,
                   help="Fraction of eligible employees with one previous SCD2 version.")
    p.add_argument("--num-projects", type=int, default=300)
    p.add_argument("--review-years", type=int, default=3,
                   help="Number of past annual review cycles to generate.")
    p.add_argument("--output-dir", default="data/generated")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--as-of-date", default=date.today().isoformat(),
                   help="Snapshot date YYYY-MM-DD. Fix it for fully repeatable output.")
    p.add_argument("--load-mysql", action="store_true",
                   help="Also load generated files into MySQL database hr_staging.")
    return p.parse_args()


def validate_source(df: pd.DataFrame) -> None:
    required = {"EmployeeNumber", "Age", "Department", "JobRole", "JobLevel",
                "MonthlyIncome", "YearsAtCompany", "Attrition"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Input CSV is missing required columns: {sorted(missing)}")
    if df["EmployeeNumber"].duplicated().any():
        raise ValueError("EmployeeNumber must be unique in the original input dataset.")


def create_synthetic_snapshot(source_df, target_rows, seed, as_of_date) -> pd.DataFrame:
    """Sample source employees and create unique synthetic employee identities."""
    rng = np.random.default_rng(seed)
    fake = Faker("en_IN")
    Faker.seed(seed)
    fake.seed_instance(seed)

    sampled = source_df.sample(n=target_rows, replace=True, random_state=seed
                               ).reset_index(drop=True)
    sampled["EmployeeNumber"] = np.arange(1, target_rows + 1, dtype=np.int64)

    # Faker generates every name; the unique id guarantees unique emails.
    names = [fake.name() for _ in range(target_rows)]
    sampled["SyntheticEmployeeName"] = names
    sampled["SyntheticEmployeeEmail"] = [
        f"employee{i}@example.test" for i in sampled["EmployeeNumber"]
    ]

    years = sampled["YearsAtCompany"].fillna(0).clip(lower=0).astype(int).to_numpy()
    extra_days = rng.integers(0, 365, size=target_rows)
    sampled["SyntheticHireDate"] = pd.to_datetime(
        [as_of_date - timedelta(days=int(y) * 365 + int(e))
         for y, e in zip(years, extra_days)]
    )

    multiplier = rng.uniform(0.90, 1.10, size=target_rows)
    sampled["MonthlyIncome"] = np.maximum(
        1, np.rint(sampled["MonthlyIncome"].to_numpy() * multiplier)
    ).astype(int)

    return sampled.drop(
        columns=[c for c in IGNORED_CONSTANT_COLUMNS if c in sampled.columns]
    )


def create_scd2_history(snapshot_df, historical_pct, seed, as_of_date) -> pd.DataFrame:
    """
    One current version per employee plus one prior version for a subset.
    Tracked attributes: Department, JobRole, JobLevel, MonthlyIncome.
    Each history event is a promotion, a department transfer or a salary bump.
    """
    rng = np.random.default_rng(seed + 1)
    fake = Faker("en_IN")
    Faker.seed(seed + 1)
    fake.seed_instance(seed + 1)

    # Valid roles per department keep Department/JobRole consistent.
    dept_roles = {
        d: sorted(g["JobRole"].dropna().unique().tolist())
        for d, g in snapshot_df.groupby("Department")
    }
    departments = list(dept_roles)

    current = snapshot_df.copy()
    current["start_date"] = pd.to_datetime(current["SyntheticHireDate"]).dt.date
    current["end_date"] = OPEN_END_DATE
    current["is_current"] = True
    current["change_reason"] = "Initial hire record"

    eligible = snapshot_df.index[
        snapshot_df["YearsAtCompany"].fillna(0).astype(int) >= 3
    ].to_numpy()
    history_count = int(round(len(eligible) * historical_pct))
    selected = (rng.choice(eligible, size=history_count, replace=False)
                if history_count > 0 else np.array([], dtype=int))

    latest_change = as_of_date - timedelta(days=180)
    previous_versions = []

    for idx in selected:
        row = snapshot_df.loc[idx]
        hire_date = pd.Timestamp(row["SyntheticHireDate"]).date()
        earliest_change = max(hire_date + timedelta(days=365),
                              as_of_date - timedelta(days=3 * 365))
        if earliest_change >= latest_change:
            continue

        change_date = fake.date_between(start_date=earliest_change,
                                        end_date=latest_change)
        change_type = str(rng.choice(CHANGE_TYPES, p=CHANGE_PROBS))
        level = int(row["JobLevel"])
        if change_type == "promotion" and level <= 1:
            change_type = "salary_bump"      # cannot promote below level 1

        previous = row.copy()
        salary = float(row["MonthlyIncome"])

        if change_type == "promotion":
            previous["JobLevel"] = level - 1
            previous["MonthlyIncome"] = max(1, int(round(salary / rng.uniform(1.10, 1.25))))
        elif change_type == "salary_bump":
            previous["MonthlyIncome"] = max(1, int(round(salary / rng.uniform(1.05, 1.15))))
        else:  # transfer: different department, role valid for that department
            others = [d for d in departments if d != row["Department"]]
            if not others:
                continue
            old_dept = str(rng.choice(others))
            previous["Department"] = old_dept
            previous["JobRole"] = str(rng.choice(dept_roles[old_dept]))

        previous["start_date"] = hire_date
        previous["end_date"] = change_date - timedelta(days=1)
        previous["is_current"] = False
        previous["change_reason"] = "Initial hire record"
        previous_versions.append(previous)

        current.at[idx, "start_date"] = change_date
        current.at[idx, "change_reason"] = change_type

    history = pd.concat([current, pd.DataFrame(previous_versions)], ignore_index=True)
    history["start_date"] = pd.to_datetime(history["start_date"])
    history["end_date"] = pd.to_datetime(history["end_date"])
    history["is_current"] = history["is_current"].astype(bool)
    return history.sort_values(["EmployeeNumber", "start_date"]).reset_index(drop=True)


def validate_history(history: pd.DataFrame) -> None:
    """SCD2 integrity: one current row per employee, no overlaps, valid ranges."""
    cur = history[history["is_current"]].groupby("EmployeeNumber").size()
    if (cur != 1).any() or cur.shape[0] != history["EmployeeNumber"].nunique():
        raise ValueError("SCD2 error: each employee must have exactly one current row.")
    if (history["end_date"] < history["start_date"]).any():
        raise ValueError("SCD2 error: end_date earlier than start_date.")
    nxt_start = history.groupby("EmployeeNumber")["start_date"].shift(-1)
    overlap = nxt_start.notna() & (history["end_date"] >= nxt_start)
    if overlap.any():
        raise ValueError("SCD2 error: overlapping version date ranges.")


def create_projects_and_assignments(snapshot_df, num_projects, seed, as_of_date):
    """Synthetic projects (per department) and employee-project assignments."""
    rng = np.random.default_rng(seed + 3)
    fake = Faker("en_IN")
    Faker.seed(seed + 3)
    fake.seed_instance(seed + 3)

    departments = sorted(snapshot_df["Department"].unique())
    proj_ids = np.arange(1, num_projects + 1)
    proj_dept = rng.choice(departments, size=num_projects)
    start_offsets = rng.integers(180, 5 * 365, size=num_projects)
    duration = rng.integers(180, 3 * 365, size=num_projects)
    starts = [as_of_date - timedelta(days=int(o)) for o in start_offsets]
    ends = [s + timedelta(days=int(d)) for s, d in zip(starts, duration)]
    status = ["Completed" if e < as_of_date else "Active" for e in ends]

    projects = pd.DataFrame({
        "ProjectID": proj_ids,
        "ProjectName": [f"{fake.word().title()} {fake.word().title()} #{i}" for i in proj_ids],
        "Department": proj_dept,
        "StartDate": pd.to_datetime(starts),
        "EndDate": pd.to_datetime([e if e < as_of_date else None for e in ends]),
        "Status": status,
        "Budget": rng.integers(50_000, 2_000_000, size=num_projects),
    })

    def assign(emp_df, slot):
        ids = np.empty(len(emp_df), dtype=np.int64)
        for dept, grp in emp_df.groupby("Department"):
            pool = projects.loc[projects["Department"] == dept, "ProjectID"].to_numpy()
            if len(pool) == 0:
                pool = proj_ids
            ids[emp_df.index.get_indexer(grp.index)] = rng.choice(pool, size=len(grp))
        out = pd.DataFrame({"EmployeeNumber": emp_df["EmployeeNumber"].to_numpy(),
                            "ProjectID": ids,
                            "HireDate": emp_df["SyntheticHireDate"].to_numpy()})
        out["IsPrimary"] = slot == "primary"
        return out

    primary = assign(snapshot_df, "primary")
    secondary_emp = snapshot_df.sample(frac=0.30, random_state=seed + 4)
    secondary = assign(secondary_emp, "secondary")

    assignments = pd.concat([primary, secondary], ignore_index=True)
    assignments = assignments.drop_duplicates(["EmployeeNumber", "ProjectID"])
    assignments = assignments.merge(projects[["ProjectID", "StartDate"]], on="ProjectID")
    base = assignments[["HireDate", "StartDate"]].max(axis=1)
    assignments["AssignedDate"] = base + pd.to_timedelta(
        rng.integers(0, 90, size=len(assignments)), unit="D")
    assignments["AllocationPct"] = np.where(
        assignments["IsPrimary"], rng.choice([50, 75, 100], size=len(assignments)), 25)
    assignments = assignments.drop(columns=["HireDate", "StartDate"])
    assignments.insert(0, "AssignmentID", np.arange(1, len(assignments) + 1))
    return projects, assignments


def create_reviews(snapshot_df, assignments, review_years, seed, as_of_date):
    """Annual performance reviews (supports Fact_PerformanceReviews / YoY trends)."""
    rng = np.random.default_rng(seed + 5)
    primary_proj = (assignments[assignments["IsPrimary"]]
                    .set_index("EmployeeNumber")["ProjectID"])
    base_rating = snapshot_df.get("PerformanceRating", pd.Series(3, index=snapshot_df.index))
    base_sat = snapshot_df.get("JobSatisfaction", pd.Series(3, index=snapshot_df.index))

    frames = []
    for offset in range(review_years, 0, -1):
        year = as_of_date.year - offset
        review_date = pd.Timestamp(year=year, month=12, day=15)
        mask = (snapshot_df["SyntheticHireDate"] <= review_date - pd.Timedelta(days=180)).to_numpy()
        sub = snapshot_df.loc[mask]
        n = len(sub)
        noise = rng.choice([-1, 0, 0, 1], size=n)
        rating = np.clip(base_rating.loc[sub.index].to_numpy() + noise, 1, 4)
        sat = np.clip(base_sat.loc[sub.index].to_numpy() + rng.choice([-1, 0, 0, 1], size=n), 1, 4)
        score = np.clip(rating * 20 + rng.normal(0, 6, size=n), 0, 100).round(1)
        frames.append(pd.DataFrame({
            "EmployeeNumber": sub["EmployeeNumber"].to_numpy(),
            "ProjectID": sub["EmployeeNumber"].map(primary_proj).to_numpy(),
            "ReviewDate": review_date,
            "ReviewYear": year,
            "PerformanceRating": rating,
            "JobSatisfaction": sat,
            "ReviewScore": score,
        }))
    reviews = pd.concat(frames, ignore_index=True)
    reviews.insert(0, "ReviewID", np.arange(1, len(reviews) + 1))
    return reviews


def load_to_mysql(files: dict[str, Path], date_cols: dict[str, list[str]]) -> None:
    """Create hr_staging and load each CSV into its staging table."""
    try:
        from sqlalchemy import create_engine, text
        from sqlalchemy.engine import URL
    except ImportError as exc:
        raise RuntimeError("MySQL loading requires SQLAlchemy.") from exc

    load_dotenv()
    host = os.getenv("MYSQL_HOST", "localhost")
    port = int(os.getenv("MYSQL_PORT", "3306"))
    user = os.getenv("MYSQL_USER", "root")
    password = os.getenv("MYSQL_PASSWORD")
    if not password:
        raise RuntimeError("Set MYSQL_PASSWORD in your .env file before using --load-mysql.")

    server_engine = create_engine(URL.create(
        "mysql+mysqlconnector", username=user, password=password, host=host, port=port))
    with server_engine.begin() as conn:
        conn.execute(text("CREATE DATABASE IF NOT EXISTS hr_staging "
                          "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"))
    server_engine.dispose()

    engine = create_engine(URL.create(
        "mysql+mysqlconnector", username=user, password=password,
        host=host, port=port, database="hr_staging"))

    for table, path in files.items():
        df = pd.read_csv(path, parse_dates=date_cols.get(table, []))
        print(f"Loading {table} ({len(df):,} rows) ...")
        df.to_sql(name=table, con=engine, if_exists="replace", index=False,
                  chunksize=5000, method="multi")
    engine.dispose()
    print("MySQL staging load completed. Database: hr_staging")


def main():
    args = parse_args()
    if args.target_rows < 100_000:
        raise ValueError("The assignment requires 100,000+ rows.")
    if not 0 <= args.historical_pct <= 1:
        raise ValueError("--historical-pct must be between 0 and 1.")

    as_of_date = date.fromisoformat(args.as_of_date)
    input_path = Path(args.input)
    if not input_path.exists():
        raise FileNotFoundError(f"Could not find {input_path}. Use --input to set its path.")

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    print(f"Reading source dataset: {input_path}")
    source_df = pd.read_csv(input_path)
    validate_source(source_df)
    print(f"Source rows: {len(source_df):,}\nGenerating {args.target_rows:,} synthetic employees ...")

    snapshot = create_synthetic_snapshot(source_df, args.target_rows, args.seed, as_of_date)
    history = create_scd2_history(snapshot, args.historical_pct, args.seed, as_of_date)
    validate_history(history)
    projects, assignments = create_projects_and_assignments(
        snapshot, args.num_projects, args.seed, as_of_date)
    reviews = create_reviews(snapshot, assignments, args.review_years, args.seed, as_of_date)

    paths = {
        "staging_employee_snapshot": out / "employee_snapshot.csv",
        "staging_employee_scd2_history": out / "employee_scd2_history.csv",
        "staging_projects": out / "projects.csv",
        "staging_project_assignments": out / "project_assignments.csv",
        "staging_performance_reviews": out / "performance_reviews.csv",
    }
    snapshot.to_csv(paths["staging_employee_snapshot"], index=False)
    history.to_csv(paths["staging_employee_scd2_history"], index=False)
    projects.to_csv(paths["staging_projects"], index=False)
    assignments.to_csv(paths["staging_project_assignments"], index=False)
    reviews.to_csv(paths["staging_performance_reviews"], index=False)

    print("\n--- Generation summary ---")
    print(f"Current employee snapshot rows : {len(snapshot):,}")
    print(f"SCD2 history rows              : {len(history):,}")
    print(f"Employees with prior versions  : "
          f"{history.loc[~history['is_current'], 'EmployeeNumber'].nunique():,}")
    print(f"Change mix                     : "
          f"{history.loc[history['is_current'] & (history['change_reason'] != 'Initial hire record'), 'change_reason'].value_counts().to_dict()}")
    print(f"Projects / assignments / reviews: "
          f"{len(projects):,} / {len(assignments):,} / {len(reviews):,}")
    print(f"Files saved in: {out}")

    if args.load_mysql:
        load_to_mysql(paths, {
            "staging_employee_snapshot": ["SyntheticHireDate"],
            "staging_employee_scd2_history": ["SyntheticHireDate", "start_date", "end_date"],
            "staging_projects": ["StartDate", "EndDate"],
            "staging_project_assignments": ["AssignedDate"],
            "staging_performance_reviews": ["ReviewDate"],
        })


if __name__ == "__main__":
    main()
