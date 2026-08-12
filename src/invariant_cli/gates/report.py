import json
from pathlib import Path

from invariant_cli.gates.engine import aggregate_verdict
from invariant_cli.gates.model import GateResult


def save_gate_report(results: list[GateResult], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    overall = aggregate_verdict(results).value
    path.write_text(
        json.dumps(
            {
                "overall": overall,
                "verdict": overall,
                "gates": [
                    {
                        "gate_id": item.gate_id,
                        "category": item.category,
                        "verdict": item.verdict.value,
                        "obligation_id": item.obligation_id,
                        "evidence": item.evidence,
                        "message": item.message,
                    }
                    for item in results
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return path
