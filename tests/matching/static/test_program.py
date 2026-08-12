from pathlib import Path

from invariant_cli.analysis.model import (
    CallResolutionKind,
    ResolutionStatus,
    SemanticTerminalKind,
)
from invariant_cli.analysis.python.analyzer import convert_program
from invariant_cli.matching.model import LogicalStateIdentity
from invariant_cli.matching.static.dataflow import trace_field_flows
from invariant_cli.matching.static.program import build_program_index, python_files


def test_unique_suffix_resolution_is_heuristic_and_cannot_be_resolved_trace(
    tmp_path: Path,
) -> None:
    (tmp_path / "service.py").write_text(
        """
def pay(state, amount):
    current = state["balance_cents"]
    updated = current - amount
    persist_balance(updated)
""".strip(),
        encoding="utf-8",
    )
    (tmp_path / "repository.py").write_text(
        """
def persist_balance(value):
    state["balance_cents"] = value

class AccountRepository:
    def store(self, amount):
        account["remaining_eur"] = amount
""".strip(),
        encoding="utf-8",
    )

    program = build_program_index(tmp_path)

    assert sorted(program.functions) == [
        "repository.AccountRepository.store",
        "repository.persist_balance",
        "service.pay",
    ]
    assert program.resolve("persist_balance").kind == CallResolutionKind.HEURISTIC
    assert program.resolve("repository.store").kind == CallResolutionKind.HEURISTIC
    trace = next(
        item
        for item in trace_field_flows(
            convert_program(program), LogicalStateIdentity("state", "balance_cents")
        )
        if item.function == "service.pay"
    )
    assert trace.operations == ("subtract",)
    assert trace.call_chain == ("pay", "persist_balance")
    assert trace.terminal_kind == SemanticTerminalKind.EXTERNAL_CALL
    assert trace.resolution == ResolutionStatus.PARTIAL
    assert trace.call_resolution == CallResolutionKind.HEURISTIC


def test_depth_limit_is_explicit(tmp_path: Path) -> None:
    (tmp_path / "chain.py").write_text(
        """
def start():
    value = state["balance"]
    first(value)

def first(value):
    second(value)

def second(value):
    state["balance"] = value
""".strip(),
        encoding="utf-8",
    )
    program = build_program_index(tmp_path)

    trace = next(
        item
        for item in trace_field_flows(
            convert_program(program),
            LogicalStateIdentity("state", "balance"),
            max_call_depth=1,
        )
        if item.function == "chain.start"
    )

    assert trace.resolution == ResolutionStatus.PARTIAL
    assert trace.call_chain == ("start", "first", "second")


def test_python_files_excludes_virtualenv_and_cache(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("", encoding="utf-8")
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "ignored.py").write_text("", encoding="utf-8")
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "ignored.py").write_text("", encoding="utf-8")

    assert python_files(tmp_path) == [tmp_path / "app.py"]
