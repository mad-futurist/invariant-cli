from invariant_cli.comparison.model import ComparisonVerdict
from invariant_cli.comparison.service import MISSING, compare_observations
from invariant_cli.observation.model import Observation, ValueChange


def test_matching_observations() -> None:
    source = [
        Observation(
            source="state.json",
            kind="json",
            changes=[
                ValueChange(
                    path="account.balance",
                    before=100,
                    after=70,
                )
            ],
        )
    ]

    target = [
        Observation(
            source="state.json",
            kind="json",
            changes=[
                ValueChange(
                    path="account.balance",
                    before=100,
                    after=70,
                )
            ],
        )
    ]

    result = compare_observations(source, target)

    assert result.matches
    assert result.differences == []


def test_detects_observation_difference() -> None:
    source = [
        Observation(
            source="state.json",
            kind="json",
            changes=[
                ValueChange(
                    path="account.balance",
                    before=100,
                    after=70,
                )
            ],
        )
    ]

    target = [
        Observation(
            source="state.json",
            kind="json",
            changes=[
                ValueChange(
                    path="account.balance",
                    before=100,
                    after=80,
                )
            ],
        )
    ]

    result = compare_observations(source, target)

    assert not result.matches
    assert len(result.differences) == 1

    difference = result.differences[0]

    assert difference.source == "state.json"
    assert difference.path == "account.balance"
    assert difference.expected == 70
    assert difference.actual == 80


def test_detects_missing_target_observation() -> None:
    source = [
        Observation(
            source="state.json",
            kind="json",
            changes=[
                ValueChange(
                    path="payment.status",
                    before="PENDING",
                    after="COMPLETED",
                )
            ],
        )
    ]

    target: list[Observation] = []

    result = compare_observations(source, target)

    assert not result.matches
    assert result.differences[0].expected == "COMPLETED"
    assert result.differences[0].actual is MISSING


def test_empty_observations_are_inconclusive() -> None:
    result = compare_observations([], [])

    assert result.verdict == ComparisonVerdict.INCONCLUSIVE
    assert not result.matches
    assert result.differences == []
