from pathlib import Path

from invariant_cli.matching.model import EntityKind, EntityRef, EvidenceEffect, EvidenceKind
from invariant_cli.matching.static.matcher import build_static_data_flow_evidence
from invariant_cli.matching.static.model import FunctionFlow
from invariant_cli.matching.static.python_ast import extract_function_flows


def _entity(namespace: str, identifier: str) -> EntityRef:
    return EntityRef(EntityKind.JSON_FIELD, namespace, identifier)


def _flows(tmp_path: Path, name: str, code: str) -> list[FunctionFlow]:
    path = tmp_path / name
    path.write_text(code.strip(), encoding="utf-8")
    return extract_function_flows(path)


def test_compatible_computation_call_chains_support_candidate(tmp_path: Path) -> None:
    source = _flows(
        tmp_path,
        "source.py",
        """
def pay(amount):
    balance = state["balance_cents"]
    remaining = balance - amount
    persist_balance(remaining)
""",
    )
    target = _flows(
        tmp_path,
        "target.py",
        """
def process_payment(value):
    current = account["remaining_eur"]
    updated = current - value
    repository.store(updated)
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
    assert evidence.attributes["source"] == {
        "function": "source.pay",
        "reads_from": "state.json#balance_cents",
        "operations": ["subtract"],
        "flows_to_call": "persist_balance",
    }
    assert evidence.attributes["target"] == {
        "function": "target.process_payment",
        "reads_from": "account.json#remaining_eur",
        "operations": ["subtract"],
        "flows_to_call": "repository.store",
    }


def test_disconnected_target_field_contradicts_candidate(tmp_path: Path) -> None:
    source = _flows(
        tmp_path,
        "source.py",
        """
def pay(amount):
    balance = state["balance_cents"]
    remaining = balance - amount
    persist_balance(remaining)
""",
    )
    target = _flows(
        tmp_path,
        "target.py",
        """
def process_payment(value, unrelated_total):
    current = account["remaining_eur"]
    logger.info(current)
    updated = unrelated_total - value
    repository.store(updated)
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
    assert evidence.attributes["reason"] == (
        "target_field_not_in_compatible_computation_call_chain"
    )
    assert evidence.attributes["target"] == {
        "function": "target.process_payment",
        "reads_from": "account.json#remaining_eur",
        "operations": [],
        "flows_to_call": "logger.info",
    }
