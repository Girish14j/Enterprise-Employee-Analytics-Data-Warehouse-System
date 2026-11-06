
import os
import time
import csv
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import URL
from sqlalchemy.exc import DBAPIError, InterfaceError, OperationalError


# ============================================================
# 1. PROJECT CONFIGURATION
# ============================================================

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data" / "generated"

load_dotenv(ROOT / ".env")

DATABASE = "hr_staging"

# Smaller batches reduce the load on the cloud database.
BATCH_SIZE = 250
SQL_CHUNK_SIZE = 250

# Maximum connection retries after a temporary failure.
MAX_RETRIES = 5
RETRY_DELAY = 5


# ============================================================
# 2. AIVEN DATABASE CONNECTION
# ============================================================

required_env = [
    "MYSQL_HOST",
    "MYSQL_USER",
    "MYSQL_PASSWORD",
]

for variable in required_env:
    if not os.getenv(variable):
        raise ValueError(f"Missing {variable} in .env file")

ca_cert = ROOT / os.getenv(
    "MYSQL_CA_CERT",
    "certificates/ca.pem"
)

if not ca_cert.exists():
    raise FileNotFoundError(
        f"CA certificate not found: {ca_cert}"
    )

connection_url = URL.create(
    "mysql+mysqlconnector",
    username=os.getenv("MYSQL_USER"),
    password=os.getenv("MYSQL_PASSWORD"),
    host=os.getenv("MYSQL_HOST"),
    port=int(os.getenv("MYSQL_PORT", "3306")),
    database=DATABASE,
)

engine = create_engine(
    connection_url,
    connect_args={
        "ssl_ca": str(ca_cert),
        "ssl_verify_cert": True,
        "ssl_verify_identity": True,
        "connection_timeout": 30,
    },
    pool_pre_ping=True,
    pool_recycle=1800,
)


# ============================================================
# 3. CSV COLUMN -> MYSQL COLUMN MAPPING
# ============================================================

employee_columns = {
    "Age": "age",
    "Attrition": "attrition",
    "BusinessTravel": "business_travel",
    "DailyRate": "daily_rate",
    "Department": "department",
    "DistanceFromHome": "distance_from_home",
    "Education": "education",
    "EducationField": "education_field",
    "EmployeeNumber": "employee_number",
    "EnvironmentSatisfaction": "environment_satisfaction",
    "Gender": "gender",
    "HourlyRate": "hourly_rate",
    "JobInvolvement": "job_involvement",
    "JobLevel": "job_level",
    "JobRole": "job_role",
    "JobSatisfaction": "job_satisfaction",
    "MaritalStatus": "marital_status",
    "MonthlyIncome": "monthly_income",
    "MonthlyRate": "monthly_rate",
    "NumCompaniesWorked": "num_companies_worked",
    "OverTime": "overtime",
    "PercentSalaryHike": "percent_salary_hike",
    "PerformanceRating": "performance_rating",
    "RelationshipSatisfaction": "relationship_satisfaction",
    "StockOptionLevel": "stock_option_level",
    "TotalWorkingYears": "total_working_years",
    "TrainingTimesLastYear": "training_times_last_year",
    "WorkLifeBalance": "work_life_balance",
    "YearsAtCompany": "years_at_company",
    "YearsInCurrentRole": "years_in_current_role",
    "YearsSinceLastPromotion": "years_since_last_promotion",
    "YearsWithCurrManager": "years_with_curr_manager",
    "SyntheticEmployeeName": "synthetic_employee_name",
    "SyntheticEmployeeEmail": "synthetic_employee_email",
    "SyntheticHireDate": "synthetic_hire_date",
}


# ============================================================
# 4. FILE AND TABLE CONFIGURATION
# ============================================================

files = [
    {
        "file": "employee_snapshot.csv",
        "table": "stg_employee_snapshot",
        "columns": employee_columns,
        "dates": ["SyntheticHireDate"],
    },
    {
        "file": "employee_scd2_history.csv",
        "table": "stg_employee_scd2_history",
        "columns": {
            **employee_columns,
            "start_date": "start_date",
            "end_date": "end_date",
            "is_current": "is_current",
            "change_reason": "change_reason",
        },
        "dates": [
            "SyntheticHireDate",
            "start_date",
            "end_date",
        ],
    },
    {
        "file": "projects.csv",
        "table": "stg_projects",
        "columns": {
            "ProjectID": "project_id",
            "ProjectName": "project_name",
            "Department": "department",
            "StartDate": "start_date",
            "EndDate": "end_date",
            "Status": "status",
            "Budget": "budget",
        },
        "dates": ["StartDate", "EndDate"],
    },
    {
        "file": "project_assignments.csv",
        "table": "stg_project_assignments",
        "columns": {
            "AssignmentID": "assignment_id",
            "EmployeeNumber": "employee_number",
            "ProjectID": "project_id",
            "IsPrimary": "is_primary",
            "AssignedDate": "assigned_date",
            "AllocationPct": "allocation_pct",
        },
        "dates": ["AssignedDate"],
    },
    {
        "file": "performance_reviews.csv",
        "table": "stg_performance_reviews",
        "columns": {
            "ReviewID": "review_id",
            "EmployeeNumber": "employee_number",
            "ProjectID": "project_id",
            "ReviewDate": "review_date",
            "ReviewYear": "review_year",
            "PerformanceRating": "performance_rating",
            "JobSatisfaction": "job_satisfaction",
            "ReviewScore": "review_score",
        },
        "dates": ["ReviewDate"],
    },
]


# ============================================================
# 5. CONNECTION ERROR DETECTION
# ============================================================

def is_connection_error(error):

    if isinstance(
        error,
        (InterfaceError, OperationalError)
    ):
        return True

    if isinstance(error, DBAPIError):

        if error.connection_invalidated:
            return True

        original_error = error.orig

        error_code = (
            original_error.args[0]
            if getattr(original_error, "args", None)
            else None
        )

        # Common MySQL connection error codes.
        if error_code in (2006, 2013, 2055):
            return True

    return False


# ============================================================
# 6. DATABASE ROW COUNT
# ============================================================

def get_table_count(table):

    with engine.connect() as connection:

        result = connection.execute(
            text(
                f"SELECT COUNT(*) "
                f"FROM `{DATABASE}`.`{table}`"
            )
        )

        return result.scalar_one()


def get_table_count_with_retry(table):

    for attempt in range(1, MAX_RETRIES + 1):

        try:
            return get_table_count(table)

        except Exception as error:

            if not is_connection_error(error):
                raise

            print(
                f"Connection lost while checking {table}. "
                f"Retry {attempt}/{MAX_RETRIES}"
            )

            engine.dispose()
            time.sleep(RETRY_DELAY)

    raise ConnectionError(
        f"Could not reconnect to Aiven after "
        f"{MAX_RETRIES} attempts."
    )


# ============================================================
# 7. COUNT CSV RECORDS
# ============================================================

def get_csv_row_count(path):

    with open(
        path,
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as csv_file:

        total_lines = sum(1 for _ in csv_file)

    # Exclude the CSV header.
    return max(0, total_lines - 1)


# ============================================================
# 8. VALIDATE CSV AND MYSQL TABLE STRUCTURE
# ============================================================

def validate_columns(connection, config, csv_columns):

    table = config["table"]
    mapping = config["columns"]

    # Validate CSV columns.
    expected_csv = set(mapping.keys())
    actual_csv = set(csv_columns)

    missing_csv = expected_csv - actual_csv
    extra_csv = actual_csv - expected_csv

    if missing_csv or extra_csv:

        raise ValueError(
            f"CSV column mismatch for {config['file']}.\n"
            f"Missing: {sorted(missing_csv)}\n"
            f"Unexpected: {sorted(extra_csv)}"
        )

    # Validate MySQL destination columns.
    inspector = inspect(connection)

    mysql_columns = {
        column["name"]
        for column in inspector.get_columns(
            table,
            schema=DATABASE
        )
    }

    expected_mysql = set(mapping.values())

    missing_mysql = expected_mysql - mysql_columns

    if missing_mysql:

        raise ValueError(
            f"MySQL table {table} is missing columns: "
            f"{sorted(missing_mysql)}"
        )


# ============================================================
# 9. VALIDATE ALL FILES BEFORE IMPORT
# ============================================================

def validate_all_files():

    print("\nValidating CSV files and MySQL tables...")

    with engine.connect() as connection:

        for config in files:

            path = DATA_DIR / config["file"]

            if not path.exists():

                raise FileNotFoundError(
                    f"CSV not found: {path}"
                )

            csv_columns = pd.read_csv(
                path,
                nrows=0,
                encoding="utf-8-sig"
            ).columns

            validate_columns(
                connection,
                config,
                csv_columns
            )

            print(
                f"Validated: {config['file']} "
                f"-> {config['table']}"
            )

    print("\nAll five files passed structural validation.")


# ============================================================
# 10. PREPARE CSV BATCH
# ============================================================

def prepare_chunk(chunk, config):

    # Rename CSV columns to MySQL column names.
    chunk = chunk.rename(
        columns=config["columns"]
    )

    # Convert date fields.
    for source_column in config["dates"]:

        target_column = config["columns"][
            source_column
        ]

        if target_column in chunk.columns:

            chunk[target_column] = pd.to_datetime(
                chunk[target_column],
                errors="raise"
            ).dt.date

    # Convert Pandas NaN values to Python None.
    chunk = chunk.astype(object).where(
        pd.notna(chunk),
        None
    )

    return chunk


# ============================================================
# 11. INSERT ONE COMMITTED BATCH
# ============================================================

def insert_batch(chunk, table):

    # A successful transaction is committed automatically.
    # If the transaction fails, it is rolled back.
    with engine.begin() as connection:

        chunk.to_sql(
            name=table,
            con=connection,
            schema=DATABASE,
            if_exists="append",
            index=False,
            chunksize=SQL_CHUNK_SIZE,
        )


# ============================================================
# 12. RESUMABLE CSV IMPORT
# ============================================================

def import_csv(config):

    path = DATA_DIR / config["file"]
    table = config["table"]

    print("\n" + "=" * 60)
    print(f"IMPORTING: {config['file']}")
    print(f"DESTINATION: {table}")
    print("=" * 60)

    total_csv_rows = get_csv_row_count(path)

    # Read the existing number of committed records.
    existing_rows = get_table_count_with_retry(table)

    if existing_rows > total_csv_rows:

        raise RuntimeError(
            f"{table} contains {existing_rows:,} rows, "
            f"but the CSV contains only {total_csv_rows:,} rows. "
            "Manual verification is required."
        )

    if existing_rows == total_csv_rows:

        print(
            f"{table} is already complete. "
            f"Skipping {existing_rows:,} rows."
        )

        return

    print(f"Total CSV rows: {total_csv_rows:,}")
    print(f"Already imported: {existing_rows:,}")
    print(
        f"Remaining rows: "
        f"{total_csv_rows - existing_rows:,}"
    )

    # This is the next CSV row to process.
    offset = existing_rows

    # Recreate the reader after a connection failure.
    while offset < total_csv_rows:

        print(
            f"\nResuming {table} from CSV row "
            f"{offset + 1:,}"
        )

        reader = pd.read_csv(
            path,
            chunksize=BATCH_SIZE,
            skiprows=range(1, offset + 1),
            encoding="utf-8-sig"
        )

        restart_reader = False

        try:

            for chunk in reader:

                chunk_length = len(chunk)

                if chunk.empty:
                    break

                prepared_chunk = prepare_chunk(
                    chunk,
                    config
                )

                committed = False

                # Retry the same batch if the connection fails.
                for attempt in range(1, MAX_RETRIES + 1):

                    try:

                        insert_batch(
                            prepared_chunk,
                            table
                        )

                        committed = True
                        break

                    except Exception as error:

                        if not is_connection_error(error):
                            raise

                        print(
                            f"\nConnection lost during "
                            f"{table} insertion."
                        )

                        print(
                            f"Retry {attempt}/{MAX_RETRIES}"
                        )

                        # Discard broken connections.
                        engine.dispose()

                        time.sleep(RETRY_DELAY)

                        # Check what MySQL actually saved.
                        saved_rows = get_table_count_with_retry(
                            table
                        )

                        if saved_rows > total_csv_rows:
                            raise RuntimeError(
                                "Database row count exceeds "
                                "the CSV row count."
                            )

                        if saved_rows > offset:

                            # The failed batch may actually have
                            # been committed before the connection
                            # was lost.
                            offset = saved_rows

                            print(
                                f"Database currently contains "
                                f"{offset:,} rows. "
                                "Rechecking from this position."
                            )

                            restart_reader = True
                            break

                        print(
                            "The batch was not saved. "
                            "It will be attempted again."
                        )

                if restart_reader:
                    break

                if not committed:

                    raise ConnectionError(
                        f"Unable to import {table} after "
                        f"{MAX_RETRIES} retries."
                    )

                # Advance only after a successful commit.
                offset += chunk_length

                print(
                    f"{table}: {offset:,} / "
                    f"{total_csv_rows:,} rows committed"
                )

            if not restart_reader:
                break

        finally:
            reader.close()

    # Verify the actual database row count.
    final_count = get_table_count_with_retry(table)

    if final_count != total_csv_rows:

        raise RuntimeError(
            f"Import verification failed for {table}. "
            f"Expected {total_csv_rows:,}, "
            f"found {final_count:,}."
        )

    print(
        f"\nSuccessfully completed {table}: "
        f"{final_count:,} rows"
    )


# ============================================================
# 13. VERIFY ALL IMPORTED TABLES
# ============================================================

def verify_imports():

    print("\n" + "=" * 60)
    print("FINAL DATABASE VERIFICATION")
    print("=" * 60)

    all_successful = True

    for config in files:

        table = config["table"]
        path = DATA_DIR / config["file"]

        expected_rows = get_csv_row_count(path)
        actual_rows = get_table_count_with_retry(table)

        status = (
            "COMPLETE"
            if actual_rows == expected_rows
            else "INCOMPLETE"
        )

        if actual_rows != expected_rows:
            all_successful = False

        print(
            f"{table}: {actual_rows:,} / "
            f"{expected_rows:,} rows - {status}"
        )

    if not all_successful:

        raise RuntimeError(
            "One or more tables have incomplete imports."
        )

    print("\nAll five CSV files were imported successfully!")


# ============================================================
# 14. MAIN EXECUTION
# ============================================================

if __name__ == "__main__":

    try:

        # Check Aiven connection.
        with engine.connect() as connection:

            result = connection.execute(
                text(
                    "SELECT DATABASE(), VERSION(), "
                    "@@hostname, @@port"
                )
            ).fetchone()

            print("\nConnected to Aiven MySQL successfully!")

            print(f"Database: {result[0]}")
            print(f"MySQL Version: {result[1]}")
            print(f"Hostname: {result[2]}")
            print(f"Port: {result[3]}")

        # Validate all CSV files and destination tables.
        validate_all_files()

        # Import or resume each CSV.
        for config in files:

            import_csv(config)

        # Verify all five tables.
        verify_imports()

    except Exception as error:

        print("\n" + "=" * 60)
        print("IMPORT STOPPED")
        print("=" * 60)

        print(f"Reason: {error}")

        print(
            "\nSuccessfully committed batches remain saved. "
            "Fix the issue and run this script again to resume."
        )

        raise

    finally:

        engine.dispose()
