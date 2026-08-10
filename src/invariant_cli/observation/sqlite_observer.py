import json
import sqlite3
from pathlib import Path
from typing import Any

from invariant_cli.observation.model import ABSENT, Observation, ValueChange
from invariant_cli.observation.observer import Observer


class SQLiteObserver(Observer):
    def accepts(self, path: Path) -> bool:
        return path.suffix.lower() in {".db", ".sqlite", ".sqlite3"}

    def observe(
        self,
        path: Path,
        before_content: bytes | None,
        after_content: bytes | None,
    ) -> Observation | None:
        before = _read_database(before_content)
        after = _read_database(after_content)
        changes: list[ValueChange] = []

        for field_path in sorted(before.keys() | after.keys()):
            before_value = before.get(field_path, ABSENT)
            after_value = after.get(field_path, ABSENT)

            if before_value == after_value:
                continue

            changes.append(
                ValueChange(
                    path=field_path,
                    before=before_value,
                    after=after_value,
                )
            )

        if not changes:
            return None

        return Observation(
            source=path.as_posix(),
            kind="sqlite",
            changes=changes,
        )


def _read_database(content: bytes | None) -> dict[str, Any]:
    if content is None:
        return {}

    connection = sqlite3.connect(":memory:")

    try:
        connection.deserialize(content)
        tables = [
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' "
                "ORDER BY name"
            )
        ]

        values: dict[str, Any] = {}
        for table in tables:
            values.update(_read_table(connection, table))
        return values
    finally:
        connection.close()


def _read_table(connection: sqlite3.Connection, table: str) -> dict[str, Any]:
    quoted_table = _quote_identifier(table)
    columns = list(connection.execute(f"PRAGMA table_info({quoted_table})"))
    column_names = [column[1] for column in columns]
    primary_keys = [column[1] for column in sorted(columns, key=lambda item: item[5]) if column[5]]

    order_columns = primary_keys or column_names
    order_by = ", ".join(_quote_identifier(column) for column in order_columns)
    rows = list(connection.execute(f"SELECT * FROM {quoted_table} ORDER BY {order_by}"))

    values: dict[str, Any] = {}
    for index, row in enumerate(rows):
        row_values = dict(zip(column_names, row, strict=True))
        identity = _row_identity(row_values, primary_keys, index)

        for column in column_names:
            values[f"{table}[{identity}].{column}"] = _normalize_value(row_values[column])

    return values


def _row_identity(values: dict[str, Any], primary_keys: list[str], index: int) -> str:
    if not primary_keys:
        return f"row={index}"

    return ",".join(
        f"{column}={json.dumps(_normalize_value(values[column]), sort_keys=True)}"
        for column in primary_keys
    )


def _normalize_value(value: Any) -> Any:
    if isinstance(value, bytes):
        return {"__sqlite_blob__": value.hex()}
    return value


def _quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'
