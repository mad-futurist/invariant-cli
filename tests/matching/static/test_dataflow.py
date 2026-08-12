from pathlib import Path

from invariant_cli.analysis.model import ProgramSemanticModel
from invariant_cli.analysis.python.analyzer import PythonSemanticAnalyzer
from invariant_cli.matching.model import EntityKind, EntityRef, EvidenceEffect, EvidenceKind
from invariant_cli.matching.static.matcher import (
    build_call_context_evidence,
    build_static_data_flow_evidence,
)


def _entity(namespace: str, identifier: str) -> EntityRef:
    return EntityRef(EntityKind.JSON_FIELD, namespace, identifier)


def _flows(tmp_path: Path, name: str, code: str) -> ProgramSemanticModel:
    path = tmp_path / name
    path.write_text(code.strip(), encoding="utf-8")
    return PythonSemanticAnalyzer().analyze(path)


def test_compatible_computation_call_chains_support_candidate(tmp_path: Path) -> None:
    source = _flows(
        tmp_path,
        "source.py",
        """
def pay(amount):
    balance = state["balance_cents"]
    remaining = balance - amount
    persist_balance(remaining)

def persist_balance(value):
    state["balance_cents"] = value
""",
    )
    target = _flows(
        tmp_path,
        "target.py",
        """
def process_payment(value):
    current = account["remaining_eur"]
    updated = current - value
    store(updated)

def store(amount):
    account["remaining_eur"] = amount
""",
    )

    evidence = build_static_data_flow_evidence(
        _entity("state.json", "balance_cents"),
        _entity("account.json", "remaining_eur"),
        source,
        target,
    )

    assert evidence is not None
    assert evidence.kind == EvidenceKind.STATIC_DATA_FLOW
    assert evidence.effect == EvidenceEffect.SUPPORTS
    assert evidence.producer == "python-dataflow-v1"
    source_attributes = evidence.attributes["source"]
    target_attributes = evidence.attributes["target"]
    assert isinstance(source_attributes, dict)
    assert isinstance(target_attributes, dict)
    assert source_attributes["call_chain"] == ["pay", "persist_balance"]
    assert target_attributes["call_chain"] == [
        "process_payment",
        "store",
    ]
    assert source_attributes["terminal_kind"] == "state_write"
    assert target_attributes["terminal_kind"] == "state_write"
    assert source_attributes["resolution"] == "resolved"
    assert target_attributes["resolution"] == "resolved"

    context = build_call_context_evidence(
        _entity("state.json", "balance_cents"),
        _entity("account.json", "remaining_eur"),
        source,
        target,
    )
    assert context is not None
    assert context.effect == EvidenceEffect.SUPPORTS
    assert context.attributes["source_terminal"] == "state_write"
    assert context.attributes["target_terminal"] == "state_write"


def test_disconnected_target_field_contradicts_candidate(tmp_path: Path) -> None:
    source = _flows(
        tmp_path,
        "source.py",
        """
def pay(amount):
    balance = state["balance_cents"]
    remaining = balance - amount
    persist_balance(remaining)

def persist_balance(value):
    state["balance_cents"] = value
""",
    )
    target = _flows(
        tmp_path,
        "target.py",
        """
def process_payment(value, unrelated_total):
    current = account["remaining_eur"]
    updated = unrelated_total - value
    store(updated)

def store(amount):
    account["remaining_eur"] = amount
""",
    )

    evidence = build_static_data_flow_evidence(
        _entity("state.json", "balance_cents"),
        _entity("account.json", "remaining_eur"),
        source,
        target,
    )

    assert evidence is not None
    assert evidence.effect == EvidenceEffect.CONTRADICTS
    assert evidence.attributes["reason"] == "incompatible_fully_resolved_behavior_chain"
    target_attributes = evidence.attributes["target"]
    assert isinstance(target_attributes, dict)
    assert target_attributes["operations"] == []
    assert target_attributes["call_chain"] == ["process_payment"]
    assert target_attributes["terminal_kind"] == "none"
    assert target_attributes["resolution"] == "resolved"


def test_unresolved_external_call_is_neutral(tmp_path: Path) -> None:
    source = _flows(
        tmp_path,
        "source.py",
        """
def pay(amount):
    balance = state["balance_cents"]
    remaining = balance - amount
    persist_balance(remaining)

def persist_balance(value):
    state["balance_cents"] = value
""",
    )
    target = _flows(
        tmp_path,
        "target.py",
        """
def process_payment(value):
    current = account["remaining_eur"]
    plugin.magic(current)
""",
    )

    evidence = build_call_context_evidence(
        _entity("state.json", "balance_cents"),
        _entity("account.json", "remaining_eur"),
        source,
        target,
    )

    assert evidence is not None
    assert evidence.effect == EvidenceEffect.NEUTRAL
    assert evidence.attributes["target_resolution"] == "unresolved"
    assert evidence.attributes["target_terminal"] == "external_call"
    assert evidence.attributes["reason"] == "unresolved_external_call"


def test_unsupported_control_flow_is_neutral_not_a_proven_dead_end(tmp_path: Path) -> None:
    source = _flows(
        tmp_path,
        "source.py",
        """
def pay(amount):
    balance = state["balance_cents"]
    updated = balance - amount
    persist_balance(updated)

def persist_balance(value):
    state["balance_cents"] = value
""",
    )
    target = _flows(
        tmp_path,
        "target.py",
        """
def process_payment(value):
    current = account["remaining_eur"]
    if current > value:
        repository.store(current - value)
""",
    )

    evidence = build_call_context_evidence(
        _entity("state.json", "balance_cents"),
        _entity("account.json", "remaining_eur"),
        source,
        target,
    )

    assert evidence is not None
    assert evidence.effect == EvidenceEffect.NEUTRAL
    assert evidence.attributes["target_resolution"] == "unresolved"
    assert evidence.attributes["reason"] == "unsupported_syntax_or_alias"


def test_return_flow_resumes_in_caller_and_reaches_state_write(tmp_path: Path) -> None:
    source = _flows(
        tmp_path,
        "source.py",
        """
def calculate(balance, amount):
    return balance - amount

def persist(value):
    state["balance_cents"] = value

def pay(amount):
    current = state["balance_cents"]
    updated = calculate(current, amount)
    persist(updated)
""",
    )
    target = _flows(
        tmp_path,
        "target.py",
        """
def compute(current, value):
    return current - value

def store(value):
    account["remaining_eur"] = value

def process(value):
    balance = account["remaining_eur"]
    result = compute(balance, value)
    store(result)
""",
    )

    evidence = build_static_data_flow_evidence(
        _entity("state.json", "balance_cents"),
        _entity("account.json", "remaining_eur"),
        source,
        target,
    )

    assert evidence is not None
    assert evidence.effect == EvidenceEffect.SUPPORTS
    source_attributes = evidence.attributes["source"]
    target_attributes = evidence.attributes["target"]
    assert isinstance(source_attributes, dict)
    assert isinstance(target_attributes, dict)
    assert source_attributes["operations"] == ["subtract"]
    assert target_attributes["operations"] == ["subtract"]
    assert source_attributes["call_chain"] == ["pay", "calculate", "persist"]
    assert target_attributes["call_chain"] == ["process", "compute", "store"]
    assert source_attributes["terminal_kind"] == "state_write"
    assert target_attributes["terminal_kind"] == "state_write"
