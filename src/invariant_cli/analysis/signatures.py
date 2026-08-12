from __future__ import annotations

from dataclasses import dataclass

from invariant_cli.analysis.model import (
    ProgramSemanticModel,
    ResolutionStatus,
    SemanticNodeKind,
)
from invariant_cli.matching.model import EntityKind, EntityRef, LogicalStateIdentity
from invariant_cli.matching.static.dataflow import trace_field_flows


@dataclass(frozen=True)
class FunctionEffect:
    kind: str
    target: LogicalStateIdentity
    owner_function: str


@dataclass(frozen=True)
class FunctionBehaviorSignature:
    function: EntityRef
    state_reads: tuple[LogicalStateIdentity, ...]
    state_writes: tuple[LogicalStateIdentity, ...]
    operations: tuple[str, ...]
    calls: tuple[str, ...]
    effects: tuple[FunctionEffect, ...]
    returns_value: bool
    resolution: ResolutionStatus


def build_function_signatures(
    model: ProgramSemanticModel,
) -> dict[str, FunctionBehaviorSignature]:
    signatures: dict[str, FunctionBehaviorSignature] = {}
    for function_id, function in sorted(model.functions.items()):
        nodes = model.function_nodes(function_id)
        direct_reads = sorted(
            {
                LogicalStateIdentity.from_semantic_label(node.label)
                for node in nodes
                if node.kind == SemanticNodeKind.STATE_READ
            }
        )
        direct_writes = {
            LogicalStateIdentity.from_semantic_label(node.label)
            for node in nodes
            if node.kind == SemanticNodeKind.STATE_WRITE
        }
        operations: set[str] = set()
        calls: set[str] = set()
        effects = {FunctionEffect("state_write", target, function_id) for target in direct_writes}
        # Resolution is scoped to the modeled state behavior. Unrelated external
        # calls (for example logging after a state write) must not poison an
        # otherwise complete state-flow signature.
        resolution = ResolutionStatus.RESOLVED

        for state in direct_reads:
            traces = [
                trace for trace in trace_field_flows(model, state) if trace.function == function_id
            ]
            for trace in traces:
                operations.update(trace.operations)
                calls.update(trace.call_chain[1:])
                if trace.terminal_kind.value == "state_write" and trace.terminal is not None:
                    effects.add(
                        FunctionEffect(
                            "state_write",
                            LogicalStateIdentity.from_semantic_label(trace.terminal),
                            _terminal_owner(model, trace.call_chain, function_id),
                        )
                    )
                resolution = _least_resolved(resolution, trace.resolution)

        signatures[function_id] = FunctionBehaviorSignature(
            function=EntityRef(
                kind=EntityKind.FUNCTION,
                namespace=function.module,
                identifier=function.name,
            ),
            state_reads=tuple(direct_reads),
            state_writes=tuple(sorted({effect.target for effect in effects})),
            operations=tuple(sorted(operations)),
            calls=tuple(sorted(calls)),
            effects=tuple(
                sorted(effects, key=lambda item: (item.kind, item.target, item.owner_function))
            ),
            returns_value=any(node.kind == SemanticNodeKind.RETURN for node in nodes),
            resolution=resolution,
        )
    return signatures


def _terminal_owner(
    model: ProgramSemanticModel,
    call_chain: tuple[str, ...],
    fallback: str,
) -> str:
    if len(call_chain) <= 1:
        return fallback
    name = call_chain[-1]
    matches = [function.id for function in model.functions.values() if function.name == name]
    return matches[0] if len(matches) == 1 else fallback


def _least_resolved(left: ResolutionStatus, right: ResolutionStatus) -> ResolutionStatus:
    order = {
        ResolutionStatus.RESOLVED: 0,
        ResolutionStatus.PARTIAL: 1,
        ResolutionStatus.UNRESOLVED: 2,
    }
    return left if order[left] >= order[right] else right
