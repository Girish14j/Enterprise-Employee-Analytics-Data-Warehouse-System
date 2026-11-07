"""MySQL connection management (Aiven, SSL-verified).

Contains two classes:
* ``DatabaseManager``    - the team's original helper (unchanged): one engine per database,
  used by the setup / import scripts.
* ``DatabaseConnection`` - Singleton for the application (managers, ETL, Streamlit).

Design
------
* ``SingletonMeta``      - thread-safe metaclass: one instance per class.
* ``DatabaseConnection`` - Singleton that owns ONE shared SQLAlchemy engine
  (connection pool) and exposes safe helpers: ``fetch_all``, ``fetch_one``,
  ``fetch_df``, ``execute``, ``insert``, ``transaction``, ``call_procedure``.
* Manager / ETL classes *inherit* from ``DatabaseConnection``.  Each subclass is
  its own singleton, but all of them share the single engine stored on
  ``DatabaseConnection`` - so the app never opens more than one pool.

Both warehouses live on the same MySQL service, so every query uses fully
qualified names (``hr_oltp.employees``, ``hr_dw.dim_employee``).  That lets the
ETL read OLTP and write the DW inside one transaction.
"""
from __future__ import annotations

import logging
import os
import tempfile
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, Iterator, List, Mapping, Optional, Sequence

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, Connection, Engine
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from src.exceptions import ConfigurationError, DatabaseError, IntegrityViolationError

logger = logging.getLogger(__name__)

STAGING_SCHEMA = "hr_staging"
OLTP_SCHEMA = "hr_oltp"
DW_SCHEMA = "hr_dw"

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


# --------------------------------------------------------------------------- #
# Team's original helper - kept unchanged for the setup / import scripts
# --------------------------------------------------------------------------- #
PROJECT_ROOT = _PROJECT_ROOT
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



# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
def _first_env(*names: str, default: Optional[str] = None) -> Optional[str]:
    for name in names:
        value = os.getenv(name)
        if value not in (None, ""):
            return value
    return default


@dataclass(frozen=True)
class DBConfig:
    """Connection settings read from environment variables (.env or Streamlit secrets)."""

    host: str
    port: int
    user: str
    password: str
    ssl_ca: str
    verify_identity: bool = True

    @classmethod
    def from_env(cls) -> "DBConfig":
        load_dotenv(_PROJECT_ROOT / ".env")
        host = _first_env("DB_HOST", "MYSQL_HOST", "AIVEN_HOST")
        user = _first_env("DB_USER", "MYSQL_USER", "AIVEN_USER")
        password = _first_env("DB_PASSWORD", "MYSQL_PASSWORD", "AIVEN_PASSWORD")
        port = int(_first_env("DB_PORT", "MYSQL_PORT", "AIVEN_PORT", default="3306"))
        missing = [n for n, v in (("DB_HOST", host), ("DB_USER", user), ("DB_PASSWORD", password)) if not v]
        if missing:
            raise ConfigurationError(f"Missing database settings: {', '.join(missing)}. See .env.example.")
        verify = _first_env("DB_SSL_VERIFY_IDENTITY", default="true").lower() in ("1", "true", "yes")
        return cls(host, port, user, password, cls._resolve_ca(), verify)  # type: ignore[arg-type]

    @staticmethod
    def _resolve_ca() -> str:
        """CA certificate from a file path, or from PEM text (for Streamlit Cloud secrets)."""
        pem = _first_env("DB_SSL_CA_PEM")
        if pem:
            handle = tempfile.NamedTemporaryFile("w", suffix=".pem", delete=False)
            handle.write(pem.replace("\\n", "\n"))
            handle.close()
            return handle.name
        path = _first_env("DB_SSL_CA", "MYSQL_CA_CERT", "MYSQL_SSL_CA", "SSL_CA", "CA_CERT_PATH")
        if not path:
            raise ConfigurationError("Set DB_SSL_CA (path to the Aiven CA file) or DB_SSL_CA_PEM.")
        candidate = Path(path)
        if not candidate.is_absolute():
            candidate = _PROJECT_ROOT / candidate
        if not candidate.exists():
            raise ConfigurationError(f"CA certificate not found: {candidate}")
        return str(candidate)


# --------------------------------------------------------------------------- #
# Singleton machinery
# --------------------------------------------------------------------------- #
class SingletonMeta(type):
    """Thread-safe metaclass: ``Cls()`` always returns the same instance of ``Cls``."""

    _instances: Dict[type, Any] = {}
    _lock = threading.RLock()

    def __call__(cls, *args: Any, **kwargs: Any) -> Any:
        if cls not in SingletonMeta._instances:
            with SingletonMeta._lock:
                if cls not in SingletonMeta._instances:
                    SingletonMeta._instances[cls] = super().__call__(*args, **kwargs)
        return SingletonMeta._instances[cls]


def _mysql_code(exc: SQLAlchemyError) -> Optional[int]:
    orig = getattr(exc, "orig", None)
    if orig is not None and getattr(orig, "args", None) and isinstance(orig.args[0], int):
        return orig.args[0]
    return None


def _clean_message(exc: SQLAlchemyError) -> str:
    orig = getattr(exc, "orig", None)
    if orig is not None and getattr(orig, "args", None):
        return " ".join(str(a) for a in orig.args)
    return str(exc).splitlines()[0]


# --------------------------------------------------------------------------- #
# DatabaseConnection
# --------------------------------------------------------------------------- #
class DatabaseConnection(metaclass=SingletonMeta):
    """Singleton wrapper around one shared SQLAlchemy engine."""

    _engine: Optional[Engine] = None
    _engine_lock = threading.Lock()
    _column_cache: Dict[tuple, Dict[str, str]] = {}

    def __init__(self) -> None:
        self._log = logging.getLogger(self.__class__.__name__)

    # -- engine ------------------------------------------------------------ #
    @classmethod
    def get_instance(cls) -> "DatabaseConnection":
        return cls()

    @staticmethod
    def _get_engine() -> Engine:
        if DatabaseConnection._engine is None:
            with DatabaseConnection._engine_lock:
                if DatabaseConnection._engine is None:
                    cfg = DBConfig.from_env()
                    url = URL.create("mysql+pymysql", username=cfg.user, password=cfg.password,
                                     host=cfg.host, port=cfg.port)
                    DatabaseConnection._engine = create_engine(
                        url,
                        pool_pre_ping=True,
                        pool_recycle=1800,
                        pool_size=5,
                        max_overflow=5,
                        connect_args={
                            "ssl_ca": cfg.ssl_ca,
                            "ssl_verify_cert": True,
                            "ssl_verify_identity": cfg.verify_identity,
                            "charset": "utf8mb4",
                        },
                    )
                    logger.info("Database engine created for %s:%s", cfg.host, cfg.port)
        return DatabaseConnection._engine

    @staticmethod
    def set_engine(engine: Engine) -> None:
        """Inject an engine (used by tests)."""
        DatabaseConnection._engine = engine
        DatabaseConnection._column_cache = {}

    @staticmethod
    def dispose() -> None:
        with DatabaseConnection._engine_lock:
            if DatabaseConnection._engine is not None:
                DatabaseConnection._engine.dispose()
                DatabaseConnection._engine = None
            DatabaseConnection._column_cache = {}

    # -- error translation -------------------------------------------------- #
    @staticmethod
    def _wrap(exc: SQLAlchemyError) -> DatabaseError:
        message = _clean_message(exc)
        logger.error("Database error: %s", message)
        if isinstance(exc, IntegrityError):
            return IntegrityViolationError(message, _mysql_code(exc))
        return DatabaseError(message, _mysql_code(exc))

    # -- connection scopes -------------------------------------------------- #
    @contextmanager
    def connection(self) -> Iterator[Connection]:
        """Read scope. Nothing is committed."""
        try:
            with self._get_engine().connect() as conn:
                yield conn
        except SQLAlchemyError as exc:
            raise self._wrap(exc) from exc

    @contextmanager
    def transaction(self) -> Iterator[Connection]:
        """Write scope. Commits on success, rolls back on ANY exception."""
        try:
            with self._get_engine().begin() as conn:
                yield conn
        except SQLAlchemyError as exc:
            raise self._wrap(exc) from exc

    # -- query helpers ------------------------------------------------------ #
    def fetch_all(self, sql: str, params: Optional[Mapping[str, Any]] = None,
                  conn: Optional[Connection] = None) -> List[Dict[str, Any]]:
        def _go(c: Connection) -> List[Dict[str, Any]]:
            return [dict(r._mapping) for r in c.execute(text(sql), dict(params or {}))]

        if conn is not None:
            return _go(conn)
        with self.connection() as c:
            return _go(c)

    def fetch_one(self, sql: str, params: Optional[Mapping[str, Any]] = None,
                  conn: Optional[Connection] = None) -> Optional[Dict[str, Any]]:
        rows = self.fetch_all(sql, params, conn)
        return rows[0] if rows else None

    def fetch_df(self, sql: str, params: Optional[Mapping[str, Any]] = None,
                 conn: Optional[Connection] = None) -> pd.DataFrame:
        def _go(c: Connection) -> pd.DataFrame:
            result = c.execute(text(sql), dict(params or {}))
            df = pd.DataFrame(result.fetchall(), columns=list(result.keys()))
            for col in df.columns:
                if df[col].dtype == object and df[col].map(lambda v: isinstance(v, Decimal)).any():
                    df[col] = pd.to_numeric(df[col].map(lambda v: float(v) if isinstance(v, Decimal) else v),
                                            errors="coerce")
            return df

        if conn is not None:
            return _go(conn)
        with self.connection() as c:
            return _go(c)

    def execute(self, sql: str, params: Optional[Mapping[str, Any]] = None,
                conn: Optional[Connection] = None) -> int:
        """Run INSERT/UPDATE/DELETE. Returns affected row count."""
        if conn is not None:
            return conn.execute(text(sql), dict(params or {})).rowcount
        with self.transaction() as c:
            return c.execute(text(sql), dict(params or {})).rowcount

    def insert(self, sql: str, params: Optional[Mapping[str, Any]] = None,
               conn: Optional[Connection] = None) -> int:
        """Run an INSERT and return ``lastrowid`` (0 when the PK is not AUTO_INCREMENT)."""
        if conn is not None:
            return int(conn.execute(text(sql), dict(params or {})).lastrowid or 0)
        with self.transaction() as c:
            return int(c.execute(text(sql), dict(params or {})).lastrowid or 0)

    def call_procedure(self, name: str, args: Sequence[Any] = ()) -> List[List[tuple]]:
        """Call a stored procedure; returns every result set it produced."""
        try:
            raw = self._get_engine().raw_connection()
        except SQLAlchemyError as exc:
            raise self._wrap(exc) from exc
        try:
            cursor = raw.cursor()
            cursor.callproc(name, tuple(args))
            sets = [list(cursor.fetchall())]
            while cursor.nextset():
                sets.append(list(cursor.fetchall()))
            raw.commit()
            return sets
        except Exception as exc:  # noqa: BLE001 - driver errors vary
            raw.rollback()
            raise DatabaseError(f"Stored procedure {name} failed: {exc}") from exc
        finally:
            raw.close()

    # -- diagnostics / schema inspection ----------------------------------- #
    def test_connection(self) -> Dict[str, Any]:
        row = self.fetch_one("SELECT 1 AS ok, VERSION() AS version, DATABASE() AS current_db")
        return row or {}

    def table_columns(self, schema: str, table: str, refresh: bool = False) -> Dict[str, str]:
        """Return ``{column_name: data_type}`` for a table (cached)."""
        key = (schema.lower(), table.lower())
        if refresh or key not in DatabaseConnection._column_cache:
            rows = self.fetch_all(
                "SELECT COLUMN_NAME AS col, DATA_TYPE AS dtype FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA = :s AND TABLE_NAME = :t ORDER BY ORDINAL_POSITION",
                {"s": schema, "t": table},
            )
            if not rows:
                raise DatabaseError(f"Table {schema}.{table} was not found (or access is denied).")
            DatabaseConnection._column_cache[key] = {r["col"]: str(r["dtype"]).lower() for r in rows}
        return DatabaseConnection._column_cache[key]

    def column_names(self, schema: str, table: str) -> List[str]:
        return list(self.table_columns(schema, table))

    def has_column(self, schema: str, table: str, column: str) -> bool:
        return column.lower() in {c.lower() for c in self.table_columns(schema, table)}


if __name__ == "__main__":
    db = DatabaseManager()
    db.test_connection()