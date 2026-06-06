from __future__ import annotations

import uuid
from datetime import datetime, timezone

from platform_capability.config import settings
from platform_capability.llm.mock_client import MockLLMClient
from platform_capability.models import (
    CrossRepoEvidenceSummary, SignalSummarizerOutput,
    InsightGeneratorOutput, LLMUsageMetadata, EvaluationResult, EvaluationFinalStatus,
)


def _valid_evidence_refs(refs: list[str], evidence_ids: set[str]) -> list[str]:
    return [r for r in refs if r in evidence_ids]


class LLMPipeline:
    def __init__(self):
        if settings.llm_provider == "mock":
            self._client = MockLLMClient()
        else:
            from platform_capability.llm.bedrock_client import BedrockLLMClient
            self._client = BedrockLLMClient()

    def run(
        self,
        summary: CrossRepoEvidenceSummary,
        scan_run_id: str,
        scan_batch_id: str,
    ) -> tuple[SignalSummarizerOutput | None, InsightGeneratorOutput | None, EvaluationResult, list[LLMUsageMetadata]]:

        evidence_ids = {item.evidence_id for item in summary.evidence_items}
        valid_cap_ids = {summary.capability_id}
        valid_repo_ids = {r.repo_id for r in summary.repo_summaries}
        usage_records: list[LLMUsageMetadata] = []
        eval_id = f"eval-{uuid.uuid4().hex[:12]}"

        # --- Step 1: SignalSummarizer ---
        signal_output = None
        for attempt in range(settings.llm_max_retry + 1):
            try:
                output, usage = self._client.summarize_signals(summary, scan_run_id)
                usage.retry_count = attempt
                usage_records.append(usage)
            except Exception as e:
                break

            # Hard gate: validate evidence refs and capability_id
            invalid_refs = [r for r in output.evidence_refs if r not in evidence_ids]
            if output.capability_id not in valid_cap_ids:
                continue  # retry
            if invalid_refs:
                # Strip invalid refs and accept with warning
                output.evidence_refs = _valid_evidence_refs(output.evidence_refs, evidence_ids)

            signal_output = output
            break

        if signal_output is None:
            return None, None, EvaluationResult(
                evaluation_id=eval_id,
                scan_batch_id=scan_batch_id,
                final_status=EvaluationFinalStatus.FAILED_FALLBACK_TO_DETERMINISTIC,
                failure_reasons=["SignalSummarizer failed all retries"],
            ), usage_records

        # --- Step 2: InsightGenerator ---
        metrics_text = (
            f"Eligible repos: {summary.aggregate_metrics.eligible_repo_count}, "
            f"Adopted: {summary.aggregate_metrics.adopted_count}, "
            f"Custom: {summary.aggregate_metrics.custom_implementation_count}, "
            f"Missing: {summary.aggregate_metrics.missing_count}"
        )
        insight_output = None
        warnings: list[str] = []

        for attempt in range(settings.llm_max_retry + 1):
            try:
                output, usage = self._client.generate_insights(
                    signal_output, metrics_text, summary, scan_run_id
                )
                usage.retry_count = attempt
                usage_records.append(usage)
            except Exception as e:
                break

            # Hard gate: validate evidence refs and repo_ids
            hallucinations = []
            for rec in output.recommendations:
                if rec.target not in valid_repo_ids and rec.target != "platform-team":
                    hallucinations.append(f"Hallucinated target: {rec.target}")
                invalid_refs = [r for r in rec.evidence_refs if r not in evidence_ids]
                rec.evidence_refs = _valid_evidence_refs(rec.evidence_refs, evidence_ids)

            if hallucinations:
                warnings.extend(hallucinations)

            insight_output = output
            break

        if insight_output is None:
            eval_result = EvaluationResult(
                evaluation_id=eval_id,
                scan_batch_id=scan_batch_id,
                final_status=EvaluationFinalStatus.ACCEPTED_WITH_WARNING,
                failure_reasons=["InsightGenerator failed, using SignalSummarizer only"],
            )
            return signal_output, None, eval_result, usage_records

        final_status = EvaluationFinalStatus.ACCEPTED_WITH_WARNING if warnings else EvaluationFinalStatus.ACCEPTED
        eval_result = EvaluationResult(
            evaluation_id=eval_id,
            scan_batch_id=scan_batch_id,
            final_status=final_status,
            warnings=warnings,
        )

        return signal_output, insight_output, eval_result, usage_records
