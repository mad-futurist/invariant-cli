from pathlib import Path

from invariant_cli.matching.static.model import FlowEdgeKind, FlowNodeKind, UsageOperation
from invariant_cli.matching.static.python_ast import extract_field_usage, extract_function_flows


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


def test_extracts_local_def_use_flow(tmp_path: Path) -> None:
    source = tmp_path / "payments.py"
    source.write_text(
        """
def pay(amount):
    balance = state["balance_cents"]
    remaining = balance - amount
    persist_balance(remaining)
""".strip(),
        encoding="utf-8",
    )

    flow = extract_function_flows(source)[0]
    nodes = {(node.kind, node.label) for node in flow.nodes}
    edges = {edge.kind for edge in flow.edges}

    assert flow.function.module == "payments"
    assert flow.function.name == "pay"
    assert (FlowNodeKind.FIELD_READ, "state.balance_cents") in nodes
    assert (FlowNodeKind.VARIABLE, "balance") in nodes
    assert (FlowNodeKind.OPERATION, "subtract") in nodes
    assert (FlowNodeKind.VARIABLE, "remaining") in nodes
    assert (FlowNodeKind.CALL, "persist_balance") in nodes
    assert edges == {
        FlowEdgeKind.READS_INTO,
        FlowEdgeKind.FLOWS_TO,
        FlowEdgeKind.ARGUMENT_TO,
    }


def test_skips_decorated_async_and_nested_functions(tmp_path: Path) -> None:
    source = tmp_path / "unsupported.py"
    source.write_text(
        """
@decorator
def decorated():
    return state["decorated"]

async def asynchronous():
    return state["async"]

def outer():
    def inner():
        return state["nested"]
""".strip(),
        encoding="utf-8",
    )

    flows = extract_function_flows(source)

    assert [flow.function.name for flow in flows] == ["outer"]
    assert flows[0].nodes == []
