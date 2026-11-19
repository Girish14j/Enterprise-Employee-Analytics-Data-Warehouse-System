import pytest

from src.exceptions import ValidationError
from src.managers.auth_manager import (
    AuthManager,
    _hash_password,
    _verify_password,
    role_for_job,
)


def test_job_role_mapping_uses_approved_titles():
    assert role_for_job("Human Resources") == "HR"
    assert role_for_job("Sales Executive") == "Executive"
    assert role_for_job(" Manager ") is None
    assert role_for_job(None) is None


def test_password_hash_verification():
    encoded = _hash_password("a-long-test-password")
    assert encoded.startswith("pbkdf2_sha256$")
    assert _verify_password("a-long-test-password", encoded)
    assert not _verify_password("incorrect-password", encoded)
    assert not _verify_password("a-long-test-password", "invalid-hash")
    assert not _verify_password("a-long-test-password", "pbkdf2_sha256$600000$!!!$!!!")


def test_authenticate_returns_access_derived_from_current_job(monkeypatch):
    manager = AuthManager()
    row = {
        "account_id": 12,
        "employee_id": 34,
        "employee_name": "Asha Rao",
        "employment_status": "Active",
        "account_active": 1,
        "job_title": "Sales Executive",
        "password_hash": _hash_password("a-long-test-password"),
    }
    monkeypatch.setattr(manager, "fetch_one", lambda *_args, **_kwargs: row)

    assert manager.authenticate("person@example.com", "incorrect-password") is None
    user = manager.authenticate("  PERSON@EXAMPLE.COM ", "a-long-test-password")

    assert user == {
        "account_id": 12,
        "employee_id": 34,
        "employee_name": "Asha Rao",
        "role": "Executive",
    }


def test_authenticate_rejects_inactive_or_unmapped_user(monkeypatch):
    manager = AuthManager()
    row = {
        "account_id": 12,
        "employee_id": 34,
        "employee_name": "Asha Rao",
        "employment_status": "Active",
        "account_active": 1,
        "job_title": "Manager",
        "password_hash": _hash_password("a-long-test-password"),
    }
    monkeypatch.setattr(manager, "fetch_one", lambda *_args, **_kwargs: row)
    assert manager.authenticate("person@example.com", "a-long-test-password") is None

    row["job_title"] = "Human Resources"
    row["employment_status"] = "Terminated"
    assert manager.authenticate("person@example.com", "a-long-test-password") is None

    row["employment_status"] = "Active"
    row["account_active"] = 0
    assert manager.authenticate("person@example.com", "a-long-test-password") is None


def test_provisioning_enforces_password_minimum_before_database_access():
    with pytest.raises(ValidationError, match="at least 12 characters"):
        AuthManager().provision_account("person@example.com", "short")
