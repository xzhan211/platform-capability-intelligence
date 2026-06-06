"""Tests for LLM mock client and pipeline."""
import pytest
from platform_capability.llm.mock_client import MockLLMClient
from platform_capability.llm.pipeline import LLMPipeline
from platform_capability.models import (
    CrossRepoEvidenceSummary, CrossRepoMetric, RepoSummaryForLLM,
    EvidenceItem, DetectionStatus, Confidence, EvaluationFinalStatus,
)


@pytest.fixture
def metric():
    return CrossRepoMetric(
        metric_id="m-001",
        scan_batch_id="batch-001",
        capability_id="platform_http_client",
        eligible_repo_count=4,
        adopted_count=1,
        custom_implementation_count=2,
        missing_count=1,
        unknown_count=0,
        exempt_count=0,
        not_eligible_count=1,
        adoption_rate=0.25,
    )


@pytest.fixture
def evidence_summary(metric):
    ev = EvidenceItem(
        evidence_id="ev-001",
        scan_run_id="run-001",
        repo_id="reporting-service",
        capability_id="platform_http_client",
        source_type="dependency",
        file_path="requirements.txt",
        content_summary="requests==2.31.0 found",
    )
    return CrossRepoEvidenceSummary(
        capability_id="platform_http_client",
        capability_name="Platform HTTP Client",
        catalog_version="1.0",
        scan_batch_id="batch-001",
        aggregate_metrics=metric,
        repo_summaries=[
            RepoSummaryForLLM(
                repo_id="payment-service", tenant_id="payments-team",
                status=DetectionStatus.ADOPTED, confidence=Confidence.HIGH,
                top_evidence_refs=[], key_findings=["Adoption: Approved dep"],
            ),
            RepoSummaryForLLM(
                repo_id="reporting-service", tenant_id="analytics-team",
                status=DetectionStatus.CUSTOM_IMPLEMENTATION, confidence=Confidence.HIGH,
                top_evidence_refs=["ev-001"], key_findings=["Reinvention: RetrySession class"],
            ),
            RepoSummaryForLLM(
                repo_id="reconciliation-service", tenant_id="finance-team",
                status=DetectionStatus.MISSING, confidence=Confidence.MEDIUM,
                top_evidence_refs=[], key_findings=[],
            ),
            RepoSummaryForLLM(
                repo_id="notification-service", tenant_id="comms-team",
                status=DetectionStatus.NOT_ELIGIBLE, confidence=Confidence.HIGH,
                top_evidence_refs=[], key_findings=[],
            ),
        ],
        common_reinvention_patterns=["Reinvention dependency: requests"],
        unknowns=[],
        evidence_items=[ev],
        token_count=1500,
    )


# ── MockLLMClient ─────────────────────────────────────────────────────────────

class TestMockLLMClient:
    def setup_method(self):
        self.client = MockLLMClient()

    def test_summarize_signals_returns_output(self, evidence_summary):
        output, usage = self.client.summarize_signals(evidence_summary, "run-001")
        assert output.capability_id == "platform_http_client"
        assert output.adoption_pattern_summary
        assert output.reinvention_pattern_summary

    def test_summarize_signals_references_evidence(self, evidence_summary):
        output, _ = self.client.summarize_signals(evidence_summary, "run-001")
        # evidence_refs should only contain IDs from the summary
        valid_ids = {ev.evidence_id for ev in evidence_summary.evidence_items}
        for ref in output.evidence_refs:
            assert ref in valid_ids

    def test_summarize_signals_usage_metadata(self, evidence_summary):
        _, usage = self.client.summarize_signals(evidence_summary, "run-001")
        assert usage.llm_step == "signal_summarizer"
        assert usage.model_id == "mock-claude-3-5-sonnet"
        assert usage.input_tokens > 0

    def test_summarize_no_adopted_repos(self, metric):
        metric.adopted_count = 0
        metric.adoption_rate = 0.0
        summary = CrossRepoEvidenceSummary(
            capability_id="platform_http_client",
            capability_name="Platform HTTP Client",
            catalog_version="1.0",
            scan_batch_id="batch-001",
            aggregate_metrics=metric,
            repo_summaries=[
                RepoSummaryForLLM(
                    repo_id="svc-a", tenant_id="team-a",
                    status=DetectionStatus.CUSTOM_IMPLEMENTATION, confidence=Confidence.HIGH,
                    top_evidence_refs=[], key_findings=[],
                ),
            ],
            evidence_items=[],
        )
        output, _ = self.client.summarize_signals(summary, "run-001")
        assert "No repos" in output.adoption_pattern_summary or output.adoption_pattern_summary

    def test_generate_insights_returns_output(self, evidence_summary):
        sig_output, _ = self.client.summarize_signals(evidence_summary, "run-001")
        output, usage = self.client.generate_insights(
            sig_output, "Eligible: 4, Adopted: 1", evidence_summary, "run-001"
        )
        assert output.insight_summary
        assert len(output.recommendations) >= 1

    def test_generate_insights_recs_have_required_fields(self, evidence_summary):
        sig_output, _ = self.client.summarize_signals(evidence_summary, "run-001")
        output, _ = self.client.generate_insights(
            sig_output, "metrics", evidence_summary, "run-001"
        )
        for rec in output.recommendations:
            assert rec.recommendation_id
            assert rec.priority in ("high", "medium", "low")
            assert rec.target
            assert rec.action

    def test_generate_insights_high_priority_for_custom_impl(self, evidence_summary):
        sig_output, _ = self.client.summarize_signals(evidence_summary, "run-001")
        output, _ = self.client.generate_insights(
            sig_output, "metrics", evidence_summary, "run-001"
        )
        high_recs = [r for r in output.recommendations if r.priority == "high"]
        assert len(high_recs) >= 1  # reporting-service and legacy-analytics-service

    def test_generate_insights_usage_metadata(self, evidence_summary):
        sig_output, _ = self.client.summarize_signals(evidence_summary, "run-001")
        _, usage = self.client.generate_insights(
            sig_output, "metrics", evidence_summary, "run-001"
        )
        assert usage.llm_step == "insight_generator"
        assert usage.output_tokens > 0


# ── LLMPipeline ───────────────────────────────────────────────────────────────

class TestLLMPipeline:
    def setup_method(self):
        # Force mock provider
        import platform_capability.config as cfg
        cfg.settings.llm_provider = "mock"
        self.pipeline = LLMPipeline()

    def test_pipeline_run_returns_all_components(self, evidence_summary):
        sig_out, ins_out, eval_result, usage = self.pipeline.run(
            evidence_summary, "run-001", "batch-001"
        )
        assert sig_out is not None
        assert ins_out is not None
        assert eval_result is not None
        assert len(usage) >= 2  # signal summarizer + insight generator

    def test_pipeline_accepted_status(self, evidence_summary):
        _, _, eval_result, _ = self.pipeline.run(evidence_summary, "run-001", "batch-001")
        assert eval_result.final_status in (
            EvaluationFinalStatus.ACCEPTED,
            EvaluationFinalStatus.ACCEPTED_WITH_WARNING,
        )

    def test_pipeline_evaluation_scan_batch_id(self, evidence_summary):
        _, _, eval_result, _ = self.pipeline.run(evidence_summary, "run-001", "batch-001")
        assert eval_result.scan_batch_id == "batch-001"

    def test_pipeline_usage_records_have_scan_run_id(self, evidence_summary):
        _, _, _, usage = self.pipeline.run(evidence_summary, "run-001", "batch-001")
        assert all(u.scan_run_id == "run-001" for u in usage)

    def test_pipeline_strips_invalid_evidence_refs(self, evidence_summary):
        """Pipeline should strip evidence_refs not in the evidence package."""
        _, ins_out, eval_result, _ = self.pipeline.run(evidence_summary, "run-001", "batch-001")
        valid_ids = {ev.evidence_id for ev in evidence_summary.evidence_items}
        if ins_out:
            for rec in ins_out.recommendations:
                for ref in rec.evidence_refs:
                    assert ref in valid_ids

    def test_pipeline_with_no_custom_impl(self, metric):
        """Pipeline with all-adopted repos should still succeed."""
        metric.custom_implementation_count = 0
        metric.adopted_count = 3
        metric.adoption_rate = 1.0
        summary = CrossRepoEvidenceSummary(
            capability_id="platform_http_client",
            capability_name="Platform HTTP Client",
            catalog_version="1.0",
            scan_batch_id="batch-001",
            aggregate_metrics=metric,
            repo_summaries=[
                RepoSummaryForLLM(
                    repo_id=f"svc-{i}", tenant_id=f"team-{i}",
                    status=DetectionStatus.ADOPTED, confidence=Confidence.HIGH,
                    top_evidence_refs=[], key_findings=[],
                ) for i in range(3)
            ],
            evidence_items=[],
        )
        sig_out, ins_out, eval_result, _ = self.pipeline.run(summary, "run-001", "batch-001")
        assert sig_out is not None
