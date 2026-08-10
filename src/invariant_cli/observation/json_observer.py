from pathlib import Path

from invariant_cli.observation import observe_json
from invariant_cli.observation.model import Observation
from invariant_cli.observation.observer import Observer


class JsonObserver(Observer):
    def accepts(self, path: Path) -> bool:
        return path.suffix.lower() == ".json"

    def observe(
        self,
        path: Path,
        before_content: str | None,
        after_content: str | None,
    ) -> Observation | None:
        before = before_content or "{}"
        after = after_content or "{}"

        if before == after:
            return None

        return observe_json(str(path), before, after)
