from __future__ import annotations

from dataclasses import dataclass

from invariant_cli.analysis.model import (
    CallResolutionKind,
    SemanticNodeKind,
)
from invariant_cli.architecture.model import ArchitectureObligation, ObligationKind
from invariant_cli.architecture.resolver import component_for_module
from invariant_cli.gates.model import GateResult, GateVerdict, VerificationContext
from invariant_cli.matching.model import LogicalStateIdentity


@dataclass(frozen=True)
class ArchitectureBindingGate:
    id: str = "architecture-artifact-binding"

    def evaluate(self, context: VerificationContext) -> GateResult:
        expected = context.contract.architecture
        actual = context.architecture
        if expected is None:
            return GateResult(
                gate_id=self.id,
                verdict=GateVerdict.INCONCLUSIVE,
                obligation_id=self.id,
                message="Contract is not bound to an architecture artifact.",
                category="architecture",
            )
        if actual is None:
            return GateResult(
                gate_id=self.id,
                verdict=GateVerdict.INCONCLUSIVE,
                obligation_id=self.id,
                message="Bound architecture artifact was not supplied.",
                category="architecture",
            )
        if expected.version != actual.version or expected.sha256 != actual.sha256:
            return GateResult(
                gate_id=self.id,
                verdict=GateVerdict.INCONCLUSIVE,
                obligation_id=self.id,
                evidence=[
                    {
                        "expected_version": expected.version,
                        "actual_version": actual.version,
                        "expected_sha256": expected.sha256,
                        "actual_sha256": actual.sha256,
                    }
                ],
                message="Architecture artifact changed after contract inference.",
                category="architecture",
            )
        return GateResult(
            gate_id=self.id,
            verdict=GateVerdict.PASS,
            obligation_id=self.id,
            evidence=[
                {"path": expected.path, "version": expected.version, "sha256": expected.sha256}
            ],
            message="Architecture artifact version and hash match the contract.",
            category="architecture",
        )


@dataclass(frozen=True)
class ArchitectureGate:
    obligation: ArchitectureObligation

    @property
    def id(self) -> str:
        return self.obligation.kind.value

    def evaluate(self, context: VerificationContext) -> GateResult:
        if context.architecture is None:
            return _result(
                self,
                GateVerdict.INCONCLUSIVE,
                "Target architecture artifact was not supplied.",
            )
        if self.obligation.kind == ObligationKind.FORBID_STATE_WRITE:
            return self._forbid_state_write(context)
        if self.obligation.kind == ObligationKind.STATE_WRITE_OWNER:
            return self._state_write_owner(context)
        return self._require_dependency(context)

    def _forbid_state_write(self, context: VerificationContext) -> GateResult:
        component_id = str(self.obligation.parameters["component"])
        violations: list[dict[str, object]] = [
            {"function": function.id, "state": node.label}
            for function in context.target_program.functions.values()
            if _component_id(context, function.module) == component_id
            for node in context.target_program.function_nodes(function.id)
            if node.kind == SemanticNodeKind.STATE_WRITE
        ]
        if violations:
            return _result(
                self,
                GateVerdict.FAIL,
                f"Component '{component_id}' writes state directly.",
                violations,
            )
        return _result(
            self,
            GateVerdict.PASS,
            f"Component '{component_id}' has no direct state writes.",
        )

    def _state_write_owner(self, context: VerificationContext) -> GateResult:
        owner = str(self.obligation.parameters["component"])
        raw_states = self.obligation.parameters.get("state", [])
        states = (
            {LogicalStateIdentity.from_semantic_label(str(item)) for item in raw_states}
            if isinstance(raw_states, list)
            else set()
        )
        writes = [
            (function, node)
            for function in context.target_program.functions.values()
            for node in context.target_program.function_nodes(function.id)
            if node.kind == SemanticNodeKind.STATE_WRITE
            and LogicalStateIdentity.from_semantic_label(node.label) in states
        ]
        if not writes:
            return _result(
                self,
                GateVerdict.INCONCLUSIVE,
                f"No writes to owned states {sorted(states)} were resolved.",
            )
        violations: list[dict[str, object]] = [
            {"function": function.id, "state": node.label}
            for function, node in writes
            if _component_id(context, function.module) != owner
        ]
        if violations:
            return _result(
                self,
                GateVerdict.FAIL,
                f"State is written outside owner component '{owner}'.",
                violations,
            )
        return _result(
            self,
            GateVerdict.PASS,
            f"All selected state writes belong to '{owner}'.",
        )

    def _require_dependency(self, context: VerificationContext) -> GateResult:
        source_component = str(self.obligation.parameters["from"])
        target_component = str(self.obligation.parameters["to"])
        unresolved = False
        evidence: list[dict[str, object]] = []
        for function in context.target_program.functions.values():
            if _component_id(context, function.module) != source_component:
                continue
            for node in context.target_program.function_nodes(function.id):
                if node.kind != SemanticNodeKind.CALL:
                    continue
                resolution = context.target_program.call_resolutions.get(node.id)
                if resolution is None or resolution.kind != CallResolutionKind.EXACT:
                    unresolved = True
                    continue
                target = context.target_program.functions.get(resolution.target_function_id or "")
                if target is not None and _component_id(context, target.module) == target_component:
                    evidence.append({"from": function.id, "to": target.id})
        if evidence:
            return _result(
                self,
                GateVerdict.PASS,
                f"Dependency '{source_component}' -> '{target_component}' is present.",
                evidence,
            )
        if unresolved:
            return _result(
                self,
                GateVerdict.INCONCLUSIVE,
                "Relevant calls could not be resolved exactly.",
            )
        return _result(
            self,
            GateVerdict.FAIL,
            f"Required dependency '{source_component}' -> '{target_component}' is missing.",
        )


def architecture_gates(
    context: VerificationContext,
) -> list[ArchitectureBindingGate | ArchitectureGate]:
    if context.architecture is None and context.contract.architecture is None:
        return []
    binding = ArchitectureBindingGate()
    if binding.evaluate(context).verdict != GateVerdict.PASS or context.architecture is None:
        return [binding]
    return [binding, *(ArchitectureGate(item) for item in context.architecture.obligations)]


def _component_id(context: VerificationContext, module: str) -> str | None:
    if context.architecture is None:
        return None
    component = component_for_module(context.architecture, module)
    return None if component is None else component.id


def _result(
    gate: ArchitectureGate,
    verdict: GateVerdict,
    message: str,
    evidence: list[dict[str, object]] | None = None,
) -> GateResult:
    return GateResult(
        gate_id=gate.id,
        verdict=verdict,
        obligation_id=gate.obligation.id,
        evidence=[] if evidence is None else evidence,
        message=message,
        category="architecture",
    )
