from collections.abc import Sequence

from invariant_cli.gates.model import Gate, GateResult, GateVerdict, VerificationContext


def run_gates(gates: Sequence[Gate], context: VerificationContext) -> list[GateResult]:
    return [gate.evaluate(context) for gate in gates]


def aggregate_verdict(results: list[GateResult]) -> GateVerdict:
    if any(result.verdict == GateVerdict.FAIL for result in results):
        return GateVerdict.FAIL
    if not results or any(result.verdict == GateVerdict.INCONCLUSIVE for result in results):
        return GateVerdict.INCONCLUSIVE
    return GateVerdict.PASS
