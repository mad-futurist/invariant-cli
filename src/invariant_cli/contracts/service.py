from __future__ import annotations

from dataclasses import dataclass

from invariant_cli.analysis.model import ProgramSemanticModel
from invariant_cli.architecture.model import ArchitectureModel
from invariant_cli.contracts.enrichment import (
    enrich_with_static_data_flow,
    enrich_with_static_usage,
)
from invariant_cli.contracts.expression_inference import infer_expression_correspondences
from invariant_cli.contracts.function_inference import infer_function_correspondences
from invariant_cli.contracts.generation import InferenceLimits
from invariant_cli.contracts.inference import infer_correspondences
from invariant_cli.contracts.model import (
    ArchitectureArtifactRef,
    CandidateTranslationContract,
    ExecutionPairRef,
    FunctionCorrespondenceStatus,
    VerificationObligation,
    VerificationObligationKind,
)
from invariant_cli.contracts.ranking import build_candidate_sets, source_entities_from_pairs
from invariant_cli.matching.static.semantic import extract_semantic_usage
from invariant_cli.observation.model import Observation


@dataclass(frozen=True)
class ContractInferenceService:
    limits: InferenceLimits = InferenceLimits()

    def infer(
        self,
        observation_pairs: list[tuple[list[Observation], list[Observation]]],
        pair_refs: list[ExecutionPairRef],
        *,
        source_program: ProgramSemanticModel | None = None,
        target_program: ProgramSemanticModel | None = None,
        architecture: ArchitectureModel | None = None,
    ) -> CandidateTranslationContract:
        candidates = infer_correspondences(observation_pairs, limits=self.limits)
        expression_candidates = infer_expression_correspondences(
            observation_pairs,
            limits=self.limits,
        )
        if source_program is not None and target_program is not None:
            candidates = enrich_with_static_usage(
                candidates,
                extract_semantic_usage(source_program),
                extract_semantic_usage(target_program),
            )
            candidates = enrich_with_static_data_flow(
                candidates,
                source_program,
                target_program,
            )
        candidate_sets = build_candidate_sets(
            candidates,
            expression_candidates,
            sources=source_entities_from_pairs(observation_pairs),
        )
        function_candidates = (
            []
            if source_program is None or target_program is None
            else infer_function_correspondences(
                source_program,
                target_program,
                candidate_sets,
            )
        )
        behavior_obligations = [
            VerificationObligation(
                id=f"preserve-{candidate.source.namespace}-{candidate.source.identifier}",
                kind=VerificationObligationKind.BEHAVIOR_PRESERVATION,
                source=candidate.source,
                target=candidate.target,
            )
            for candidate in function_candidates
            if candidate.status == FunctionCorrespondenceStatus.CANDIDATE
            and candidate.mapped_state_reads
            and candidate.mapped_state_writes
        ]
        architecture_obligations = [
            VerificationObligation(
                id=item.id,
                kind=VerificationObligationKind.ARCHITECTURE,
                rule=item.id,
            )
            for item in (() if architecture is None else architecture.obligations)
        ]
        return CandidateTranslationContract(
            version=7,
            paired_executions=pair_refs,
            correspondences=candidates,
            expression_correspondences=expression_candidates,
            candidate_sets=candidate_sets,
            function_correspondences=function_candidates,
            obligations=[*behavior_obligations, *architecture_obligations],
            architecture=(
                None
                if architecture is None
                else ArchitectureArtifactRef(
                    path=architecture.artifact_path,
                    version=architecture.version,
                    sha256=architecture.sha256,
                )
            ),
        )
