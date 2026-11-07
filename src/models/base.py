"""Entity base class with encapsulated, self-validating fields."""
from __future__ import annotations

from typing import Any, ClassVar, Dict, Mapping, Optional

from src.exceptions import ValidationError
from src.models.validators import Validator


class Field:
    """Data descriptor: stores the value privately (``_name``) and validates on every assignment."""

    def __init__(self, validator: Optional[Validator] = None, required: bool = False):
        self.validator = validator
        self.required = required
        self.name = ""
        self.private = ""
        self.label = ""

    def __set_name__(self, owner: type, name: str) -> None:
        self.name = name
        self.private = f"_{name}"
        self.label = name.replace("_", " ").capitalize()

    def __get__(self, obj: Any, objtype: Optional[type] = None) -> Any:
        if obj is None:
            return self
        return getattr(obj, self.private, None)

    def __set__(self, obj: Any, value: Any) -> None:
        if value is None or (isinstance(value, str) and not value.strip()):
            setattr(obj, self.private, None)
            return
        setattr(obj, self.private, self.validator(value, self.label) if self.validator else value)


class Entity:
    """Base for Employee / Project / Review."""

    _fields: ClassVar[Dict[str, Field]] = {}

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        fields: Dict[str, Field] = {}
        for base in reversed(cls.__mro__):
            for name, value in vars(base).items():
                if isinstance(value, Field):
                    fields[name] = value
        cls._fields = fields

    def __init__(self, **values: Any) -> None:
        unknown = set(values) - set(self._fields)
        if unknown:
            raise TypeError(f"{type(self).__name__} got unknown field(s): {', '.join(sorted(unknown))}")
        for name in self._fields:
            setattr(self, name, values.get(name))  # runs the validator

    # -- behaviour shared by all entities ----------------------------------- #
    def validate(self) -> "Entity":
        """Check required fields. Subclasses extend this with cross-field rules."""
        missing = [f.label for n, f in self._fields.items() if f.required and getattr(self, n) is None]
        if missing:
            raise ValidationError(f"Required: {', '.join(missing)}.")
        return self

    def to_dict(self) -> Dict[str, Any]:
        return {name: getattr(self, name) for name in self._fields}

    @classmethod
    def from_row(cls, row: Mapping[str, Any]):
        """Build from a trusted DB row (bypasses validators; extra columns are ignored)."""
        obj = cls.__new__(cls)
        for name, field in cls._fields.items():
            setattr(obj, field.private, row.get(name))
        return obj

    def __repr__(self) -> str:
        shown = ", ".join(f"{k}={v!r}" for k, v in self.to_dict().items() if v is not None)
        return f"{type(self).__name__}({shown})"
