from pathlib import Path

import yaml

from invariant_cli.architecture.model import (
    ArchitectureModel,
    ArchitectureObligation,
    Component,
    ObligationKind,
)


def load_architecture(path: Path) -> ArchitectureModel:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Architecture artifact must be a mapping.")
    version = int(raw.get("version", 0))
    if version != 1:
        raise ValueError(f"Unsupported architecture version: {version}.")

    components = tuple(_component(item) for item in _items(raw, "components"))
    component_ids = {component.id for component in components}
    if len(component_ids) != len(components):
        raise ValueError("Architecture component ids must be unique.")

    obligations = tuple(_obligation(item) for item in _items(raw, "rules"))
    if len({item.id for item in obligations}) != len(obligations):
        raise ValueError("Architecture rule ids must be unique.")
    _validate_components(obligations, component_ids)
    return ArchitectureModel(version=version, components=components, obligations=obligations)


def _component(raw: object) -> Component:
    item = _mapping(raw, "component")
    modules = item.get("modules", [])
    if not isinstance(modules, list) or not all(isinstance(value, str) for value in modules):
        raise ValueError("Component modules must be a list of strings.")
    return Component(id=str(item["id"]), modules=tuple(modules))


def _obligation(raw: object) -> ArchitectureObligation:
    item = _mapping(raw, "rule")
    return ArchitectureObligation(
        id=str(item["id"]),
        kind=ObligationKind(str(item["kind"])),
        parameters={str(key): value for key, value in item.items() if key not in {"id", "kind"}},
    )


def _items(raw: dict[object, object], key: str) -> list[object]:
    value = raw.get(key, [])
    if not isinstance(value, list):
        raise ValueError(f"Architecture '{key}' must be a list.")
    return value


def _mapping(raw: object, label: str) -> dict[object, object]:
    if not isinstance(raw, dict):
        raise ValueError(f"Architecture {label} must be a mapping.")
    return raw


def _validate_components(
    obligations: tuple[ArchitectureObligation, ...],
    component_ids: set[str],
) -> None:
    for obligation in obligations:
        names = {
            str(value)
            for key, value in obligation.parameters.items()
            if key in {"component", "from", "to"}
        }
        missing = names - component_ids
        if missing:
            raise ValueError(
                f"Rule '{obligation.id}' references unknown components: {sorted(missing)}."
            )
