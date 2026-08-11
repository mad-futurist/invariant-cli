import ast
from pathlib import Path

from invariant_cli.matching.static.model import (
    AnalysisResolution,
    FieldUsage,
    FlowEdge,
    FlowEdgeKind,
    FlowNode,
    FlowNodeKind,
    FunctionFlow,
    FunctionRef,
    UsageOperation,
)


def extract_field_usage(path: Path) -> dict[str, FieldUsage]:
    tree = ast.parse(
        path.read_text(encoding="utf-8"),
        filename=str(path),
    )

    collector = _UsageCollector()
    collector.visit(tree)

    return {
        identifier: FieldUsage(
            identifier=identifier,
            operations=operations,
        )
        for identifier, operations in collector.operations.items()
    }


def extract_function_flows(path: Path, *, module: str | None = None) -> list[FunctionFlow]:
    tree = ast.parse(
        path.read_text(encoding="utf-8"),
        filename=str(path),
    )
    module_name = module or path.stem
    flows: list[FunctionFlow] = []

    for function_name, node, is_method in _functions(tree):
        if not node.decorator_list:
            flows.append(
                _FunctionFlowBuilder(
                    module_name,
                    function_name,
                    node,
                    is_method=is_method,
                ).build()
            )

    return flows


class _FunctionFlowBuilder:
    def __init__(
        self,
        module: str,
        function_name: str,
        function: ast.FunctionDef,
        *,
        is_method: bool,
    ) -> None:
        self.function = FunctionRef(module=module, name=function_name)
        self.body = function.body
        parameters = [*function.args.posonlyargs, *function.args.args]
        if is_method and parameters and parameters[0].arg in {"self", "cls"}:
            parameters = parameters[1:]
        self.parameters = tuple(parameter.arg for parameter in parameters)
        self.nodes: list[FlowNode] = []
        self.edges: list[FlowEdge] = []
        self.definitions: dict[str, str] = {}
        self.sequence = 0
        self.resolution = AnalysisResolution.RESOLVED

    def build(self) -> FunctionFlow:
        for parameter in self.parameters:
            self.definitions[parameter] = self._node(
                FlowNodeKind.PARAMETER,
                parameter,
                self.body[0] if self.body else ast.Pass(),
            )
        for statement in self.body:
            self._statement(statement)
        return FunctionFlow(
            function=self.function,
            parameters=self.parameters,
            nodes=self.nodes,
            edges=self.edges,
            resolution=self.resolution,
        )

    def _statement(self, statement: ast.stmt) -> None:
        if isinstance(statement, ast.Assign) and len(statement.targets) == 1:
            self._assign(statement.targets[0], statement.value)
        elif isinstance(statement, ast.AnnAssign) and statement.value is not None:
            self._assign(statement.target, statement.value)
        elif isinstance(statement, ast.AugAssign):
            self._augmented_assign(statement)
        elif isinstance(statement, ast.Expr):
            self._expression(statement.value)
        elif isinstance(statement, ast.Return):
            self._return(statement)
        else:
            self.resolution = AnalysisResolution.UNRESOLVED

    def _assign(self, target: ast.expr, value: ast.expr) -> None:
        sources = self._expression(value)
        if isinstance(target, ast.Name):
            variable = self._node(FlowNodeKind.VARIABLE, target.id, target)
            self.definitions[target.id] = variable
            for source in sources:
                source_node = self._node_by_id(source)
                edge_kind = (
                    FlowEdgeKind.READS_INTO
                    if source_node.kind == FlowNodeKind.FIELD_READ
                    else FlowEdgeKind.FLOWS_TO
                )
                self._edge(source, variable, edge_kind)
        elif isinstance(target, ast.Subscript):
            field = _field_label(target)
            if field is None:
                return
            write = self._node(FlowNodeKind.FIELD_WRITE, field, target)
            for source in sources:
                self._edge(source, write, FlowEdgeKind.WRITES_TO)

    def _augmented_assign(self, statement: ast.AugAssign) -> None:
        operation = _operation(statement.op)
        if operation is None:
            return

        inputs: list[str] = []
        if isinstance(statement.target, ast.Name):
            inputs.extend(self._name(statement.target))
        elif isinstance(statement.target, ast.Subscript):
            field = _field_label(statement.target)
            if field is None:
                return
            inputs.append(self._node(FlowNodeKind.FIELD_READ, field, statement.target))
        else:
            return

        inputs.extend(self._expression(statement.value))
        operation_node = self._node(FlowNodeKind.OPERATION, operation.value, statement)
        for source in inputs:
            self._edge(source, operation_node, FlowEdgeKind.FLOWS_TO)

        if isinstance(statement.target, ast.Name):
            variable = self._node(FlowNodeKind.VARIABLE, statement.target.id, statement.target)
            self.definitions[statement.target.id] = variable
            self._edge(operation_node, variable, FlowEdgeKind.FLOWS_TO)
        else:
            field = _field_label(statement.target)
            if field is not None:
                write = self._node(FlowNodeKind.FIELD_WRITE, field, statement.target)
                self._edge(operation_node, write, FlowEdgeKind.WRITES_TO)

    def _expression(self, expression: ast.expr) -> list[str]:
        if isinstance(expression, ast.Name):
            return self._name(expression)
        if isinstance(expression, ast.Subscript):
            field = _field_label(expression)
            if field is None:
                self.resolution = AnalysisResolution.UNRESOLVED
                return []
            return [self._node(FlowNodeKind.FIELD_READ, field, expression)]
        if isinstance(expression, ast.BinOp):
            operation = _operation(expression.op)
            if operation is None:
                self.resolution = AnalysisResolution.UNRESOLVED
                return []
            inputs = self._expression(expression.left) + self._expression(expression.right)
            operation_node = self._node(FlowNodeKind.OPERATION, operation.value, expression)
            for source in inputs:
                self._edge(source, operation_node, FlowEdgeKind.FLOWS_TO)
            return [operation_node]
        if isinstance(expression, ast.Call):
            name = _call_name(expression.func)
            if name is None:
                self.resolution = AnalysisResolution.UNRESOLVED
                return []
            call = self._node(FlowNodeKind.CALL, name, expression)
            for slot, argument in enumerate(expression.args):
                for source in self._expression(argument):
                    self._edge(
                        source,
                        call,
                        FlowEdgeKind.ARGUMENT_TO,
                        argument_slot=slot,
                    )
            for keyword in expression.keywords:
                for source in self._expression(keyword.value):
                    self._edge(
                        source,
                        call,
                        FlowEdgeKind.ARGUMENT_TO,
                        argument_slot=None,
                    )
            return [call]
        if not isinstance(expression, ast.Constant):
            self.resolution = AnalysisResolution.UNRESOLVED
        return []

    def _return(self, statement: ast.Return) -> None:
        returned = self._node(FlowNodeKind.RETURN, "return", statement)
        if statement.value is not None:
            for source in self._expression(statement.value):
                self._edge(source, returned, FlowEdgeKind.FLOWS_TO)

    def _name(self, expression: ast.Name) -> list[str]:
        existing = self.definitions.get(expression.id)
        if existing is not None:
            return [existing]
        variable = self._node(FlowNodeKind.VARIABLE, expression.id, expression)
        self.definitions[expression.id] = variable
        return [variable]

    def _node(self, kind: FlowNodeKind, label: str, syntax: ast.AST) -> str:
        self.sequence += 1
        node_id = (
            f"{self.function.module}:{self.function.name}:"
            f"{getattr(syntax, 'lineno', 0)}:{getattr(syntax, 'col_offset', 0)}:"
            f"{kind.value}:{self.sequence}"
        )
        self.nodes.append(FlowNode(id=node_id, kind=kind.value, label=label))
        return node_id

    def _edge(
        self,
        source: str,
        target: str,
        kind: FlowEdgeKind,
        *,
        argument_slot: int | None = None,
    ) -> None:
        self.edges.append(
            FlowEdge(
                source=source,
                target=target,
                kind=kind.value,
                argument_slot=argument_slot,
            )
        )

    def _node_by_id(self, node_id: str) -> FlowNode:
        return next(node for node in reversed(self.nodes) if node.id == node_id)


def _functions(tree: ast.Module) -> list[tuple[str, ast.FunctionDef, bool]]:
    result: list[tuple[str, ast.FunctionDef, bool]] = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            result.append((node.name, node, False))
        elif isinstance(node, ast.ClassDef):
            result.extend(
                (f"{node.name}.{member.name}", member, True)
                for member in node.body
                if isinstance(member, ast.FunctionDef)
            )
    return result


class _UsageCollector(ast.NodeVisitor):
    def __init__(self) -> None:
        self.operations: dict[str, set[UsageOperation]] = {}

    def visit_Subscript(self, node: ast.Subscript) -> None:
        identifier = _string_key(node)

        if identifier is not None:
            if isinstance(node.ctx, ast.Load):
                self._add(identifier, UsageOperation.READ)
            elif isinstance(node.ctx, ast.Store):
                self._add(identifier, UsageOperation.WRITE)

        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        if isinstance(node.target, ast.Subscript):
            identifier = _string_key(node.target)

            if identifier is not None:
                self._add(identifier, UsageOperation.READ)
                self._add(identifier, UsageOperation.WRITE)

                operation = _operation(node.op)
                if operation is not None:
                    self._add(identifier, operation)

        self.generic_visit(node)

    def visit_BinOp(self, node: ast.BinOp) -> None:
        operation = _operation(node.op)

        if operation is not None:
            for identifier in _field_identifiers(node):
                self._add(identifier, operation)

        self.generic_visit(node)

    def visit_Compare(self, node: ast.Compare) -> None:
        for identifier in _field_identifiers(node):
            self._add(identifier, UsageOperation.COMPARE)

        self.generic_visit(node)

    def _add(self, identifier: str, operation: UsageOperation) -> None:
        self.operations.setdefault(identifier, set()).add(operation)


def _string_key(node: ast.Subscript) -> str | None:
    slice_node = node.slice

    if isinstance(slice_node, ast.Constant) and isinstance(slice_node.value, str):
        return slice_node.value

    return None


def _field_label(node: ast.Subscript) -> str | None:
    key = _string_key(node)
    if key is None:
        return None
    container = _expression_name(node.value)
    return f"{container}.{key}" if container is not None else key


def _expression_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        owner = _expression_name(node.value)
        return f"{owner}.{node.attr}" if owner is not None else node.attr
    if isinstance(node, ast.Subscript):
        return _field_label(node)
    return None


def _call_name(node: ast.expr) -> str | None:
    return _expression_name(node)


def _field_identifiers(node: ast.AST) -> set[str]:
    return {
        identifier
        for child in ast.walk(node)
        if isinstance(child, ast.Subscript)
        if (identifier := _string_key(child)) is not None
    }


def _operation(operator: ast.operator) -> UsageOperation | None:
    if isinstance(operator, ast.Add):
        return UsageOperation.ADD
    if isinstance(operator, ast.Sub):
        return UsageOperation.SUBTRACT
    if isinstance(operator, ast.Mult):
        return UsageOperation.MULTIPLY
    if isinstance(operator, ast.Div):
        return UsageOperation.DIVIDE
    return None
