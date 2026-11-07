"""Base class of the Data Access Layer."""
from __future__ import annotations

from typing import Any, Dict, Iterable, Mapping, Optional

from sqlalchemy.engine import Connection

from src.database.db_manager import DW_SCHEMA, OLTP_SCHEMA, DatabaseConnection


class BaseManager(DatabaseConnection):
    """Inherits the Singleton connection layer and adds helpers shared by all managers."""

    OLTP = OLTP_SCHEMA
    DW = DW_SCHEMA

    def _next_id(self, table: str, id_column: str, conn: Connection) -> int:
        """Next primary key for tables whose PK is NOT AUTO_INCREMENT.

        ``FOR UPDATE`` locks the index range inside the caller's transaction, so two
        simultaneous inserts cannot receive the same id.
        """
        row = self.fetch_one(
            f"SELECT COALESCE(MAX(`{id_column}`), 0) + 1 AS next_id FROM {self.OLTP}.`{table}` FOR UPDATE",
            conn=conn,
        )
        return int(row["next_id"]) if row else 1

    def _existing_columns(self, schema: str, table: str) -> Dict[str, str]:
        """lower-case name -> real column name."""
        return {c.lower(): c for c in self.column_names(schema, table)}

    def _filter_to_columns(self, row: Mapping[str, Any], schema: str, table: str) -> Dict[str, Any]:
        """Drop keys that are not real columns of the live table (logs what was dropped)."""
        cols = self._existing_columns(schema, table)
        kept = {cols[k.lower()]: v for k, v in row.items() if k.lower() in cols}
        dropped = sorted(set(row) - {k for k in row if k.lower() in cols})
        if dropped:
            self._log.warning("Columns not present in %s.%s were skipped: %s", schema, table, ", ".join(dropped))
        return kept

    @staticmethod
    def _same(a: Any, b: Any) -> bool:
        if a is None or b is None:
            return a is b
        try:
            return abs(float(a) - float(b)) < 1e-9
        except (TypeError, ValueError):
            return str(a) == str(b)

    @staticmethod
    def _col_list(columns: Iterable[str]) -> str:
        return ", ".join(f"`{c}`" for c in columns)
