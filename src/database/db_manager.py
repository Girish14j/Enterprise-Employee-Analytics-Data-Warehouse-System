import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, URL, text

# Load environment variables from the project root
PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")


class DatabaseManager:

    def __init__(self):
        self.host = os.getenv("MYSQL_HOST")
        self.port = int(os.getenv("MYSQL_PORT", "3306"))
        self.username = os.getenv("MYSQL_USER")
        self.password = os.getenv("MYSQL_PASSWORD")

        certificate_path = os.getenv("MYSQL_CA_CERT")
        self.ca_certificate = PROJECT_ROOT / certificate_path

        if not self.ca_certificate.exists():
            raise FileNotFoundError(
                f"MySQL CA certificate not found: {self.ca_certificate}"
            )

        if not all([
            self.host,
            self.username,
            self.password
        ]):
            raise ValueError("Missing MySQL connection credentials")

    def get_engine(self, database):
        url = URL.create(
            drivername="mysql+mysqlconnector",
            username=self.username,
            password=self.password,
            host=self.host,
            port=self.port,
            database=database
        )

        return create_engine(
            url,
            connect_args={
                "ssl_ca": str(self.ca_certificate),
                "ssl_verify_cert": True,
                "ssl_verify_identity": True
            },
            pool_pre_ping=True
        )

    def test_connection(self, database="hr_staging"):
        engine = self.get_engine(database)

        try:
            with engine.connect() as connection:
                result = connection.execute(
                    text("SELECT DATABASE(), VERSION()")
                )
                print("Database connection successful!")
                print(result.fetchone())

        finally:
            engine.dispose()


if __name__ == "__main__":
    db = DatabaseManager()
    db.test_connection()
