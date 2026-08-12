from invariant_cli.architecture.model import ArchitectureModel, Component


def component_for_module(model: ArchitectureModel, module: str) -> Component | None:
    matches = [
        component
        for component in model.components
        if any(module == prefix or module.startswith(f"{prefix}.") for prefix in component.modules)
    ]
    return matches[0] if len(matches) == 1 else None
