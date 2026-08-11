from pathlib import Path

from invariant_cli.analysis.model import (
    CallResolutionKind,
    SemanticEdgeKind,
    SemanticNodeKind,
)
from invariant_cli.analysis.python.analyzer import PythonSemanticAnalyzer


def test_converts_python_flow_to_neutral_semantic_model(tmp_path: Path) -> None:
    path = tmp_path / "app.py"
    path.write_text(
        """
def persist(value):
    state["balance"] = value

def pay(amount):
    current = state["balance"]
    updated = current - amount
    persist(updated)
""".strip(),
        encoding="utf-8",
    )

    model = PythonSemanticAnalyzer().analyze(path)

    assert model.metadata["analyzer"] == "python-ast-v1"
    assert sorted(model.functions) == ["app.pay", "app.persist"]
    assert {node.kind for node in model.nodes} >= {
        SemanticNodeKind.PARAMETER,
        SemanticNodeKind.STATE_READ,
        SemanticNodeKind.STATE_WRITE,
        SemanticNodeKind.OPERATION,
        SemanticNodeKind.CALL,
    }
    call = next(node for node in model.nodes if node.kind == SemanticNodeKind.CALL)
    resolution = model.call_resolutions[call.id]
    assert resolution.kind == CallResolutionKind.EXACT
    assert resolution.target_function_id == "app.persist"
    assert any(
        edge.target == call.id
        and edge.kind == SemanticEdgeKind.ARGUMENT_TO
        and edge.argument_slot == 0
        for edge in model.edges
    )


def test_includes_executable_module_level_code(tmp_path: Path) -> None:
    path = tmp_path / "script.py"
    path.write_text('state["balance"] -= payment\n', encoding="utf-8")

    model = PythonSemanticAnalyzer().analyze(path)

    assert sorted(model.functions) == ["script.<module>"]
    assert {node.kind for node in model.nodes} >= {
        SemanticNodeKind.STATE_READ,
        SemanticNodeKind.STATE_WRITE,
        SemanticNodeKind.OPERATION,
    }


def test_unique_cross_module_suffix_is_heuristic_not_exact(tmp_path: Path) -> None:
    (tmp_path / "service.py").write_text(
        """
def pay(value):
    repository.store(value)
""".strip(),
        encoding="utf-8",
    )
    (tmp_path / "repository.py").write_text(
        """
class Repository:
    def store(self, value):
        state["balance"] = value
""".strip(),
        encoding="utf-8",
    )

    model = PythonSemanticAnalyzer().analyze(tmp_path)
    call = next(node for node in model.nodes if node.kind == SemanticNodeKind.CALL)

    assert model.call_resolutions[call.id].kind == CallResolutionKind.HEURISTIC


def test_duplicate_suffix_is_ambiguous(tmp_path: Path) -> None:
    (tmp_path / "caller.py").write_text(
        """
def run(value):
    backend.store(value)
""".strip(),
        encoding="utf-8",
    )
    for module, class_name in [("cache", "Cache"), ("repository", "Repository")]:
        (tmp_path / f"{module}.py").write_text(
            f"""
class {class_name}:
    def store(self, value):
        state["value"] = value
""".strip(),
            encoding="utf-8",
        )

    model = PythonSemanticAnalyzer().analyze(tmp_path)
    call = next(node for node in model.nodes if node.kind == SemanticNodeKind.CALL)
    resolution = model.call_resolutions[call.id]

    assert resolution.kind == CallResolutionKind.AMBIGUOUS
    assert resolution.target_function_id is None
    assert resolution.candidates == ("cache.Cache.store", "repository.Repository.store")
