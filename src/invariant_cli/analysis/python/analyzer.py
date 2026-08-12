from pathlib import Path

from invariant_cli.analysis.model import (
    ProgramSemanticModel,
    ResolutionStatus,
    SemanticCallResolution,
    SemanticEdge,
    SemanticEdgeKind,
    SemanticFunction,
    SemanticNode,
    SemanticNodeKind,
)
from invariant_cli.matching.static.model import (
    AnalysisResolution,
    FlowEdge,
    FlowEdgeKind,
    FlowNode,
    FlowNodeKind,
    FunctionFlow,
)
from invariant_cli.matching.static.program import ProgramIndex, build_program_index, python_files
from invariant_cli.matching.static.python_ast import extract_module_flow


class PythonSemanticAnalyzer:
    name = "python-ast-v1"

    def analyze(self, path: Path) -> ProgramSemanticModel:
        files = python_files(path)
        root = path if path.is_dir() else path.parent
        program = build_program_index(path)
        module_flows = [
            flow
            for source in files
            if (flow := extract_module_flow(source, module=_module_name(source, root))).nodes
        ]
        program = ProgramIndex.from_flows(
            [*program.functions.values(), *module_flows],
            aliases=program.aliases,
        )
        return convert_program(program, path=path, analyzer=self.name)


def convert_program(
    program: ProgramIndex,
    *,
    path: Path | None = None,
    analyzer: str = "python-ast-v1",
) -> ProgramSemanticModel:
    functions: dict[str, SemanticFunction] = {}
    nodes: list[SemanticNode] = []
    edges: list[SemanticEdge] = []
    call_resolutions: dict[str, SemanticCallResolution] = {}

    for function_id, flow in sorted(program.functions.items()):
        functions[function_id] = SemanticFunction(
            id=function_id,
            module=flow.function.module,
            name=flow.function.name,
            parameters=flow.parameters,
            resolution=_resolution(flow.resolution),
        )
        nodes.extend(_semantic_node(node, function_id) for node in flow.nodes)
        edges.extend(_semantic_edge(edge) for edge in flow.edges)

        for node in flow.nodes:
            if node.kind != FlowNodeKind.CALL:
                continue
            resolution = program.resolve(node.label, caller_module=flow.function.module)
            call_resolutions[node.id] = SemanticCallResolution(
                call_node_id=node.id,
                kind=resolution.kind,
                target_function_id=(
                    None if resolution.target is None else _function_id(resolution.target)
                ),
                candidates=tuple(sorted(_function_id(item) for item in resolution.candidates)),
            )

    metadata: dict[str, object] = {"analyzer": analyzer}
    if path is not None:
        metadata["path"] = str(path)
        metadata["files"] = [str(item) for item in python_files(path)]

    return ProgramSemanticModel(
        functions=functions,
        nodes=sorted(nodes, key=lambda node: node.id),
        edges=sorted(
            edges,
            key=lambda edge: (
                edge.source,
                edge.target,
                edge.kind.value,
                -1 if edge.argument_slot is None else edge.argument_slot,
            ),
        ),
        call_resolutions=call_resolutions,
        metadata=metadata,
    )


def _semantic_node(node: FlowNode, function_id: str) -> SemanticNode:
    kinds = {
        FlowNodeKind.FIELD_READ.value: SemanticNodeKind.STATE_READ,
        FlowNodeKind.PARAMETER.value: SemanticNodeKind.PARAMETER,
        FlowNodeKind.VARIABLE.value: SemanticNodeKind.VALUE,
        FlowNodeKind.OPERATION.value: SemanticNodeKind.OPERATION,
        FlowNodeKind.CALL.value: SemanticNodeKind.CALL,
        FlowNodeKind.FIELD_WRITE.value: SemanticNodeKind.STATE_WRITE,
        FlowNodeKind.RETURN.value: SemanticNodeKind.RETURN,
    }
    return SemanticNode(
        id=node.id,
        function_id=function_id,
        kind=kinds[FlowNodeKind(node.kind).value],
        label=node.label,
    )


def _semantic_edge(edge: FlowEdge) -> SemanticEdge:
    kind = (
        SemanticEdgeKind.ARGUMENT_TO
        if edge.kind == FlowEdgeKind.ARGUMENT_TO
        else SemanticEdgeKind.FLOWS_TO
    )
    return SemanticEdge(
        source=edge.source,
        target=edge.target,
        kind=kind,
        argument_slot=edge.argument_slot,
    )


def _resolution(resolution: AnalysisResolution) -> ResolutionStatus:
    if resolution == AnalysisResolution.RESOLVED:
        return ResolutionStatus.RESOLVED
    return ResolutionStatus.UNRESOLVED


def _function_id(flow: FunctionFlow) -> str:
    return f"{flow.function.module}.{flow.function.name}"


def _module_name(path: Path, root: Path) -> str:
    relative = path.relative_to(root).with_suffix("")
    return ".".join(relative.parts)
