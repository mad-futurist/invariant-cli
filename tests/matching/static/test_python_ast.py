from pathlib import Path

from invariant_cli.matching.static.model import UsageOperation
from invariant_cli.matching.static.python_ast import extract_field_usage


def test_extracts_usage_from_python_subscripts(tmp_path: Path) -> None:
    source = tmp_path / "app.py"
    source.write_text(
        """
def update(state: dict[str, int], payment: int) -> None:
    state["balance_cents"] -= payment
    state["doubled"] = state["balance_cents"] * 2
    if state["balance_cents"] > 0:
        state["status"] = "active"
""".strip(),
        encoding="utf-8",
    )

    usage = extract_field_usage(source)

    assert usage["balance_cents"].operations == {
        UsageOperation.READ,
        UsageOperation.WRITE,
        UsageOperation.SUBTRACT,
        UsageOperation.MULTIPLY,
        UsageOperation.COMPARE,
    }
    assert usage["doubled"].operations == {UsageOperation.WRITE}
    assert usage["status"].operations == {UsageOperation.WRITE}


def test_ignores_non_literal_subscript_keys(tmp_path: Path) -> None:
    source = tmp_path / "app.py"
    source.write_text(
        """
def read(state: dict[str, int], key: str) -> int:
    return state[key]
""".strip(),
        encoding="utf-8",
    )

    assert extract_field_usage(source) == {}
