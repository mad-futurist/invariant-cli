from typing import Protocol

from invariant_cli.capture.model import CaptureContext, ProbeResult
from invariant_cli.execution.model import Execution


class CaptureProbe(Protocol):
    def start(self, context: CaptureContext) -> "ProbeSession": ...


class ProbeSession(Protocol):
    def stop(self, execution: Execution) -> ProbeResult: ...
