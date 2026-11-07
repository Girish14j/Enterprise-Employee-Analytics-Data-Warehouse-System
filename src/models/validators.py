"""Reusable field validators. Each factory returns ``fn(value, label) -> cleaned_value``."""
from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Callable, Iterable

from src.exceptions import ValidationError

Validator = Callable[[Any, str], Any]
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")


def text(max_len: int, min_len: int = 1) -> Validator:
    def _v(value: Any, label: str) -> str:
        s = str(value).strip()
        if not (min_len <= len(s) <= max_len):
            raise ValidationError(f"{label} must be {min_len}-{max_len} characters long.")
        return s
    return _v


def email(max_len: int = 255) -> Validator:
    def _v(value: Any, label: str) -> str:
        s = str(value).strip().lower()
        if len(s) > max_len or not EMAIL_RE.match(s):
            raise ValidationError(f"{label} is not a valid email address.")
        return s
    return _v


def int_range(low: int, high: int) -> Validator:
    def _v(value: Any, label: str) -> int:
        try:
            if isinstance(value, float) and not value.is_integer():
                raise ValueError
            number = int(value)
        except (TypeError, ValueError):
            raise ValidationError(f"{label} must be a whole number.") from None
        if not (low <= number <= high):
            raise ValidationError(f"{label} must be between {low} and {high}.")
        return number
    return _v


def number_range(low: float, high: float) -> Validator:
    def _v(value: Any, label: str) -> float:
        try:
            number = float(Decimal(str(value)))
        except (InvalidOperation, ValueError):
            raise ValidationError(f"{label} must be a number.") from None
        if not (low <= number <= high):
            raise ValidationError(f"{label} must be between {low:g} and {high:g}.")
        return number
    return _v


def choice(options: Iterable[str]) -> Validator:
    canon = {o.lower(): o for o in options}

    def _v(value: Any, label: str) -> str:
        key = str(value).strip().lower()
        if key not in canon:
            raise ValidationError(f"{label} must be one of: {', '.join(canon.values())}.")
        return canon[key]
    return _v


def date_value() -> Validator:
    def _v(value: Any, label: str) -> date:
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        try:
            return date.fromisoformat(str(value).strip())
        except ValueError:
            raise ValidationError(f"{label} must be a valid date (YYYY-MM-DD).") from None
    return _v
