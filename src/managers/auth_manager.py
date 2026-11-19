"""Authentication and account provisioning for application users."""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from typing import Any, Dict, Optional

from src.exceptions import DuplicateRecordError, RecordNotFoundError, ValidationError
from src.managers.base_manager import BaseManager

_PASSWORD_SCHEME = "pbkdf2_sha256"
_PASSWORD_ITERATIONS = 600_000
_PASSWORD_SALT_BYTES = 16
_PASSWORD_DIGEST_BYTES = 32
_MIN_PASSWORD_LENGTH = 12

_ROLE_BY_JOB = {
    "human resources": "HR",
    "sales executive": "Executive",
}


def role_for_job(job_title: Any) -> Optional[str]:
    """Return app access only for the explicitly approved employee job titles."""
    if not isinstance(job_title, str):
        return None
    return _ROLE_BY_JOB.get(job_title.strip().casefold())


def _hash_password(password: str) -> str:
    salt = secrets.token_bytes(_PASSWORD_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, _PASSWORD_ITERATIONS, _PASSWORD_DIGEST_BYTES
    )
    return "$".join((
        _PASSWORD_SCHEME,
        str(_PASSWORD_ITERATIONS),
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(digest).decode("ascii"),
    ))


def _verify_password(password: str, stored_hash: str) -> bool:
    try:
        scheme, iteration_text, salt_text, digest_text = stored_hash.split("$")
        iterations = int(iteration_text)
        salt = base64.b64decode(salt_text, validate=True)
        expected = base64.b64decode(digest_text, validate=True)
    except (AttributeError, TypeError, ValueError):
        return False
    if (scheme != _PASSWORD_SCHEME or iterations != _PASSWORD_ITERATIONS
            or len(salt) != _PASSWORD_SALT_BYTES or len(expected) != _PASSWORD_DIGEST_BYTES):
        return False
    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations, len(expected))
    return hmac.compare_digest(actual, expected)


class AuthManager(BaseManager):
    """Look up credentials and derive app access from the employee's current job role."""

    def _user_row(self, where: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return self.fetch_one(
            f"SELECT a.account_id, a.username, a.password_hash, a.is_active AS account_active, "
            f"e.employee_id, e.employee_name, e.employment_status, jr.job_title "
            f"FROM {self.OLTP}.user_accounts a "
            f"JOIN {self.OLTP}.employees e ON e.employee_id = a.employee_id "
            f"JOIN {self.OLTP}.job_roles jr ON jr.job_role_id = e.job_role_id "
            f"WHERE {where}",
            params,
        )

    @staticmethod
    def _to_session_user(row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not row.get("account_active") or row.get("employment_status") != "Active":
            return None
        role = role_for_job(row.get("job_title"))
        if role is None:
            return None
        return {
            "account_id": int(row["account_id"]),
            "employee_id": int(row["employee_id"]),
            "employee_name": str(row["employee_name"]),
            "role": role,
        }

    def authenticate(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        username = (username or "").strip().lower()
        if not username or not password:
            return None
        row = self._user_row("LOWER(a.username) = :username", {"username": username})
        if not row or not _verify_password(password, row.get("password_hash")):
            return None
        return self._to_session_user(row)

    def get_session_user(self, account_id: int) -> Optional[Dict[str, Any]]:
        """Revalidate account status and current job role on each Streamlit page run."""
        row = self._user_row("a.account_id = :account_id", {"account_id": account_id})
        return self._to_session_user(row) if row else None

    def provision_account(self, username: str, password: str) -> int:
        """Create an account for an active employee with an approved job role."""
        username = (username or "").strip().lower()
        if not username:
            raise ValidationError("Enter the employee's work email.")
        if len(password) < _MIN_PASSWORD_LENGTH:
            raise ValidationError(f"Password must be at least {_MIN_PASSWORD_LENGTH} characters.")

        with self.transaction() as conn:
            employee = self.fetch_one(
                f"SELECT e.employee_id, e.employment_status, jr.job_title "
                f"FROM {self.OLTP}.employees e "
                f"JOIN {self.OLTP}.job_roles jr ON jr.job_role_id = e.job_role_id "
                f"WHERE LOWER(e.email) = :username FOR UPDATE",
                {"username": username},
                conn,
            )
            if not employee:
                raise RecordNotFoundError("No employee has that work email.")
            if employee.get("employment_status") != "Active":
                raise ValidationError("Only active employees can be given an account.")
            if role_for_job(employee.get("job_title")) is None:
                raise ValidationError("The employee's job role is not approved for application access.")
            existing = self.fetch_one(
                f"SELECT account_id FROM {self.OLTP}.user_accounts "
                "WHERE employee_id = :employee_id OR LOWER(username) = :username",
                {"employee_id": employee["employee_id"], "username": username},
                conn,
            )
            if existing:
                raise DuplicateRecordError("An account already exists for this employee or email.")
            return self.insert(
                f"INSERT INTO {self.OLTP}.user_accounts (employee_id, username, password_hash) "
                "VALUES (:employee_id, :username, :password_hash)",
                {
                    "employee_id": employee["employee_id"],
                    "username": username,
                    "password_hash": _hash_password(password),
                },
                conn,
            )
