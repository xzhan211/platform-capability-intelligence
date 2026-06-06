from __future__ import annotations

import time
import uuid

from platform_capability.models import (
    CrossRepoEvidenceSummary, SignalSummarizerOutput,
    InsightGeneratorOutput, LLMRecommendation, LLMUsageMetadata,
    DetectionStatus,
)


class MockLLMClient:
    """Pre-scripted mock LLM for local demo without Bedrock."""

    model_id = "mock-claude-3-5-sonnet"

    def summarize_signals(
        self, summary: CrossRepoEvidenceSummary, scan_run_id: str
    ) -> tuple[SignalSummarizerOutput, LLMUsageMetadata]:
        start = time.time()

        custom = [r for r in summary.repo_summaries if r.status == DetectionStatus.CUSTOM_IMPLEMENTATION]
        adopted = [r for r in summary.repo_summaries if r.status == DetectionStatus.ADOPTED]
        missing = [r for r in summary.repo_summaries if r.status == DetectionStatus.MISSING]

        adopt_summary = (
            f"{len(adopted)} repo(s) correctly use the approved {summary.capability_name} capability."
            if adopted else f"No repos are using the approved {summary.capability_name} capability."
        )
        reinv_summary = (
            f"{len(custom)} repo(s) appear to implement custom alternatives: "
            + ", ".join(r.repo_id for r in custom) + ". "
            + ("Common pattern: " + "; ".join(summary.common_reinvention_patterns[:2]) if summary.common_reinvention_patterns else "")
            if custom else f"No custom implementations detected."
        )

        all_refs = [ref for r in summary.repo_summaries for ref in r.top_evidence_refs[:1]]

        output = SignalSummarizerOutput(
            capability_id=summary.capability_id,
            adoption_pattern_summary=adopt_summary,
            reinvention_pattern_summary=reinv_summary,
            evidence_refs=all_refs[:6],
            unknowns=summary.unknowns[:3],
            confidence="high" if not summary.unknowns else "medium",
        )
        usage = LLMUsageMetadata(
            scan_run_id=scan_run_id,
            llm_step="signal_summarizer",
            model_id=self.model_id,
            input_tokens=len(str(summary.model_dump())) // 4,
            output_tokens=len(str(output.model_dump())) // 4,
            latency_ms=int((time.time() - start) * 1000),
        )
        return output, usage

    def generate_insights(
        self,
        signal_summary: SignalSummarizerOutput,
        metrics_text: str,
        summary: CrossRepoEvidenceSummary,
        scan_run_id: str,
    ) -> tuple[InsightGeneratorOutput, LLMUsageMetadata]:
        start = time.time()

        m = summary.aggregate_metrics
        custom = [r for r in summary.repo_summaries if r.status == DetectionStatus.CUSTOM_IMPLEMENTATION]
        missing = [r for r in summary.repo_summaries if r.status == DetectionStatus.MISSING]

        insight = (
            f"The {summary.capability_name} capability has a {m.adoption_rate * 100:.0f}% adoption rate "
            f"among {m.eligible_repo_count} eligible repo(s). "
        )
        if custom:
            insight += (
                f"{len(custom)} repo(s) implement custom alternatives instead of the platform capability "
                f"({', '.join(r.repo_id for r in custom)}). "
            )
            if summary.common_reinvention_patterns:
                insight += f"The most common reinvention pattern is: {summary.common_reinvention_patterns[0]}. "
        if missing:
            insight += (
                f"{len(missing)} eligible repo(s) are missing the capability entirely "
                f"({', '.join(r.repo_id for r in missing)}). "
            )
        insight += "Platform team should prioritize outreach to repos with custom implementations."

        recs: list[LLMRecommendation] = []
        for i, repo in enumerate(custom):
            recs.append(LLMRecommendation(
                recommendation_id=f"rec-{uuid.uuid4().hex[:6]}",
                priority="high",
                target=repo.repo_id,
                action=f"Migrate custom {summary.capability_name} implementation to use the approved platform capability. Contact the {repo.tenant_id} team to schedule migration.",
                evidence_refs=repo.top_evidence_refs[:2],
            ))
        for repo in missing:
            recs.append(LLMRecommendation(
                recommendation_id=f"rec-{uuid.uuid4().hex[:6]}",
                priority="medium",
                target=repo.repo_id,
                action=f"Onboard {repo.repo_id} to the {summary.capability_name} capability. Review eligibility and provide integration documentation to the {repo.tenant_id} team.",
                evidence_refs=repo.top_evidence_refs[:1],
            ))
        if custom or missing:
            recs.append(LLMRecommendation(
                recommendation_id=f"rec-{uuid.uuid4().hex[:6]}",
                priority="medium",
                target="platform-team",
                action=f"Review {summary.capability_name} onboarding documentation and add a migration guide for teams currently using custom implementations.",
                evidence_refs=[],
            ))

        output = InsightGeneratorOutput(
            insight_summary=insight,
            recommendations=recs,
            unknowns=summary.unknowns[:2],
        )
        usage = LLMUsageMetadata(
            scan_run_id=scan_run_id,
            llm_step="insight_generator",
            model_id=self.model_id,
            input_tokens=len(str(signal_summary.model_dump()) + metrics_text) // 4,
            output_tokens=len(str(output.model_dump())) // 4,
            latency_ms=int((time.time() - start) * 1000),
        )
        return output, usage
