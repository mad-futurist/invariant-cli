import json
from pathlib import Path

from invariant_cli.observation import observe_json
from invariant_cli.observation.model import ABSENT, Observation, ValueChange
from invariant_cli.observation.observer import ResourceDecoder


class JsonObserver(ResourceDecoder):
    def accepts(self, path: Path) -> bool:
        return path.suffix.lower() == ".json"

    def decode(
        self,
        path: Path,
        before_content: bytes | None,
        after_content: bytes | None,
    ) -> Observation | None:
        if before_content is None or after_content is None:
            before = ABSENT if before_content is None else json.loads(before_content)
            after = ABSENT if after_content is None else json.loads(after_content)

            if before is after:
                return None

            return Observation(
                source=path.as_posix(),
                kind="json",
                changes=[ValueChange(path="$", before=before, after=after)],
            )

        before = before_content.decode("utf-8")
        after = after_content.decode("utf-8")

        if before == after:
            return None

        return observe_json(path.as_posix(), before, after)
