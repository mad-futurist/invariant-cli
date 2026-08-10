from invariant_cli.observation.json_diff import diff_json
from invariant_cli.observation.model import Observation


def observe_json(path: str | None, before_content: str, after_content: str) -> Observation:
    import json

    before = json.loads(before_content)
    after = json.loads(after_content)

    return Observation(
        source=path or "",
        kind="json",
        changes=diff_json(before, after),
    )
