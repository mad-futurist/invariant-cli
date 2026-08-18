from collections.abc import Sequence

from invariant_cli.gates.model import Gate, GateResult, VerificationContext
from invariant_cli.verification.engine import aggregate_verdict


def run_gates(gates: Sequence[Gate], context: VerificationContext) -> list[GateResult]:
    return [gate.evaluate(context) for gate in gates]


__all__ = ["aggregate_verdict", "run_gates"]
