from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import replace
from pathlib import Path

from invariant_cli.specifications.model import (
    Requirement,
    RequirementSource,
    Specification,
)

_ADAPTER = "spec-kitty"
_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_BOLD_HEADING = re.compile(r"^\*\*([^*]+)\*\*\s*$")
_REQUIREMENT = re.compile(r"^\s*-\s+\*\*(FR-\d{3})\*\*:\s*(.+?)\s*$")
_ADDRESSED = re.compile(r"^\*\*Functional Requirements Addressed\*\*:\s*(.+?)\s*$")
_REQUIREMENT_ID = re.compile(r"FR-\d{3}")
_WORK_PACKAGE_ID = re.compile(r'^work_package_id:\s*["\']?([^"\'\s]+)')


class SpecKittyAdapterError(ValueError):
    """Raised when pinned Spec Kitty artifacts are structurally invalid or incomplete."""


class SpecKittyAdapter:
    def load(
        self,
        repository_root: Path,
        *,
        mission: str,
        work_package: str,
        requirement_ids: Iterable[str] | None = None,
    ) -> Specification:
        repository_root = repository_root.resolve()
        mission_root = repository_root / "kitty-specs" / mission
        spec_path = mission_root / "spec.md"
        task_path = _find_work_package(mission_root / "tasks", work_package)
        requirements = _parse_requirements(spec_path, repository_root, mission)
        addressed, task_heading = _parse_work_package(task_path, work_package)
        selected = tuple(requirement_ids) if requirement_ids is not None else addressed
        if len(selected) != len(set(selected)):
            raise SpecKittyAdapterError("Requested requirement IDs must be unique.")
        missing_from_work_package = sorted(set(selected) - set(addressed))
        if missing_from_work_package:
            raise SpecKittyAdapterError(
                f"Requirements are not assigned to {work_package}: {missing_from_work_package}"
            )

        task_source = RequirementSource(
            adapter=_ADAPTER,
            artifact=task_path.relative_to(repository_root).as_posix(),
            heading=task_heading,
            mission=mission,
            work_package=work_package,
        )
        normalized: list[Requirement] = []
        for requirement_id in selected:
            try:
                requirement = requirements[requirement_id]
            except KeyError as exc:
                raise SpecKittyAdapterError(
                    f"Requirement {requirement_id} is assigned to {work_package} "
                    "but absent from spec.md."
                ) from exc
            normalized.append(replace(requirement, sources=(*requirement.sources, task_source)))

        return Specification(
            id=f"spec-kitty:{mission}:{work_package}",
            adapter=_ADAPTER,
            mission=mission,
            work_package=work_package,
            requirements=tuple(normalized),
        )


def _parse_requirements(
    path: Path,
    repository_root: Path,
    mission: str,
) -> dict[str, Requirement]:
    text = _read(path)
    headings: dict[int, str] = {}
    requirements: dict[str, Requirement] = {}
    for line in text.splitlines():
        heading_match = _HEADING.match(line)
        if heading_match:
            level = len(heading_match.group(1))
            headings = {key: value for key, value in headings.items() if key < level}
            headings[level] = heading_match.group(2).strip()
            continue
        bold_heading_match = _BOLD_HEADING.match(line)
        if bold_heading_match:
            headings = {key: value for key, value in headings.items() if key < 4}
            headings[4] = bold_heading_match.group(1).strip()
            continue
        requirement_match = _REQUIREMENT.match(line)
        if requirement_match is None:
            continue
        requirement_id, requirement_text = requirement_match.groups()
        if requirement_id in requirements:
            raise SpecKittyAdapterError(f"Duplicate requirement in {path}: {requirement_id}")
        source = RequirementSource(
            adapter=_ADAPTER,
            artifact=path.relative_to(repository_root).as_posix(),
            heading=" > ".join(headings[level] for level in sorted(headings) if level > 1),
            mission=mission,
        )
        requirements[requirement_id] = Requirement(
            id=requirement_id,
            text=requirement_text.strip(),
            sources=(source,),
        )
    if not requirements:
        raise SpecKittyAdapterError(f"No functional requirements found in {path}.")
    return requirements


def _parse_work_package(path: Path, expected_id: str) -> tuple[tuple[str, ...], str]:
    text = _read(path)
    declared_id: str | None = None
    current_heading = ""
    addressed: tuple[str, ...] = ()
    addressed_heading = ""
    for line in text.splitlines():
        if declared_id is None:
            id_match = _WORK_PACKAGE_ID.match(line)
            if id_match:
                declared_id = id_match.group(1)
        heading_match = _HEADING.match(line)
        if heading_match:
            current_heading = heading_match.group(2).strip()
            continue
        addressed_match = _ADDRESSED.match(line)
        if addressed_match:
            addressed = tuple(_REQUIREMENT_ID.findall(addressed_match.group(1)))
            addressed_heading = current_heading
    if declared_id != expected_id:
        raise SpecKittyAdapterError(
            f"Work package mismatch in {path}: expected {expected_id}, found {declared_id}."
        )
    if not addressed:
        raise SpecKittyAdapterError(f"No addressed requirements found in {path}.")
    return addressed, addressed_heading


def _find_work_package(tasks_root: Path, work_package: str) -> Path:
    matches = sorted(tasks_root.glob(f"{work_package}*.md"))
    if len(matches) != 1:
        raise SpecKittyAdapterError(
            f"Expected one task artifact for {work_package} in {tasks_root}, found {len(matches)}."
        )
    return matches[0]


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SpecKittyAdapterError(f"Cannot read Spec Kitty artifact {path}: {exc}") from exc


__all__ = ["SpecKittyAdapter", "SpecKittyAdapterError"]
