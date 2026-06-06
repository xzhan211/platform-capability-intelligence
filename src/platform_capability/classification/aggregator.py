from __future__ import annotations

import uuid
from collections import Counter

from platform_capability.models import (
    CapabilityDetectionResult, CrossRepoMetric, CrossRepoEvidenceSummary,
    RepoSummaryForLLM, DetectionStatus, EvidenceItem, Capability,
)


class CrossRepoAggregator:
    def aggregate(
        self,
        results: list[CapabilityDetectionResult],
        capability: Capability,
        scan_batch_id: str,
        evidence_items: dict[str, EvidenceItem],  # evidence_id -> item
        max_evidence_tokens: int = 60_000,
    ) -> tuple[CrossRepoMetric, CrossRepoEvidenceSummary]:

        status_counts = Counter(r.status for r in results)

        # Eligible = all except NOT_ELIGIBLE and EXEMPT
        eligible = [
            r for r in results
            if r.status not in (DetectionStatus.NOT_ELIGIBLE, DetectionStatus.EXEMPT)
        ]
        adopted = status_counts[DetectionStatus.ADOPTED]
        adoption_rate = adopted / len(eligible) if eligible else 0.0

        metric = CrossRepoMetric(
            metric_id=f"metric-{uuid.uuid4().hex[:8]}",
            scan_batch_id=scan_batch_id,
            capability_id=capability.capability_id,
            eligible_repo_count=len(eligible),
            adopted_count=adopted,
            custom_implementation_count=status_counts[DetectionStatus.CUSTOM_IMPLEMENTATION],
            missing_count=status_counts[DetectionStatus.MISSING],
            unknown_count=status_counts[DetectionStatus.UNKNOWN],
            exempt_count=status_counts[DetectionStatus.EXEMPT],
            not_eligible_count=status_counts[DetectionStatus.NOT_ELIGIBLE],
            adoption_rate=round(adoption_rate, 3),
        )

        # Build per-repo summaries with top evidence refs
        repo_summaries: list[RepoSummaryForLLM] = []
        all_selected_evidence: list[EvidenceItem] = []
        common_reinvention: list[str] = []

        for result in results:
            top_refs = result.evidence_refs[:3]
            key_findings = []

            for sig in result.adoption_signals[:2]:
                key_findings.append(f"Adoption: {sig.description}")
            for sig in result.reinvention_signals[:2]:
                key_findings.append(f"Reinvention: {sig.description}")
                common_reinvention.append(sig.description)

            repo_summaries.append(RepoSummaryForLLM(
                repo_id=result.repo_id,
                tenant_id=result.tenant_id,
                status=result.status,
                confidence=result.confidence,
                top_evidence_refs=top_refs,
                key_findings=key_findings,
            ))

            for ev_id in top_refs:
                if ev_id in evidence_items:
                    all_selected_evidence.append(evidence_items[ev_id])

        # Deduplicate common reinvention patterns
        seen = set()
        unique_reinvention = []
        for p in common_reinvention:
            key = p[:60]
            if key not in seen:
                seen.add(key)
                unique_reinvention.append(p)

        unknowns = [
            f"{r.repo_id}: {'; '.join(r.unknowns)}"
            for r in results if r.unknowns
        ]

        summary = CrossRepoEvidenceSummary(
            capability_id=capability.capability_id,
            capability_name=capability.name,
            catalog_version=capability.catalog_version,
            scan_batch_id=scan_batch_id,
            aggregate_metrics=metric,
            repo_summaries=repo_summaries,
            common_reinvention_patterns=unique_reinvention[:5],
            unknowns=unknowns,
            evidence_items=all_selected_evidence,
            token_count=self._estimate_tokens(repo_summaries, all_selected_evidence),
        )

        return metric, summary

    @staticmethod
    def _estimate_tokens(summaries: list[RepoSummaryForLLM], items: list[EvidenceItem]) -> int:
        # Rough estimate: 1 token ≈ 4 characters
        text = " ".join(
            f"{s.repo_id} {s.status} {' '.join(s.key_findings)}" for s in summaries
        ) + " ".join(i.content_summary + i.raw_content for i in items)
        return len(text) // 4
