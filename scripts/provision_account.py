"""Create a login for an eligible employee.

Run from the repository root with ``python scripts/provision_account.py``.
"""
from __future__ import annotations

import getpass
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.exceptions import AppError  # noqa: E402
from src.managers.auth_manager import AuthManager  # noqa: E402


def main() -> int:
    username = input("Employee work email: ").strip()
    password = getpass.getpass("Password (at least 12 characters): ")
    confirmation = getpass.getpass("Confirm password: ")
    if password != confirmation:
        print("Passwords do not match.")
        return 1
    try:
        account_id = AuthManager().provision_account(username, password)
    except AppError as exc:
        print(f"Account was not created: {exc}")
        return 1
    print(f"Account created (id {account_id}). The employee can now sign in with {username.lower()}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
