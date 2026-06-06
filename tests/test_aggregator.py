"""Tests for classification/aggregator.py"""
import pytest
from platform_capability.classification.aggregator import CrossRepoAggregator
from platform_capability.models import (
    CapabilityDetectionResult, DetectionStatus, Confidence,
    DetectionSignal, EvidenceItem, SignalType, SignalWeight,
)


@pytest.fixture
def aggregator():
    return CrossRepoAggregator()


def _make_result(repo_id: str, tenant_id: str, status: DetectionStatus, ev_ids: list[str] = None) -> CapabilityDetectionResult:
    from uuid import uuid4
    return CapabilityDetectionResult(
        detection_id=f"det-{uuid4().hex[:8]}",
        scan_run_id="run-001",
        repo_id=repo_id,
        tenant_id=tenant_id,
        capability_id="platform_http_client",
        status=status,
        confidence=Confidence.HIGH if status in (DetectionStatus.ADOPTED, DetectionStatus.NOT_ELIGIBLE) else Confidence.MEDIUM,
        evidence_refs=ev_ids or [],
        adoption_signals=[
            DetectionSignal(
                signal_id="sig-a", repo_id=repo_id,
                capability_id="platform_http_client",
                signal_type=SignalType.ADOPTION, weight=SignalWeight.HIGH,
                evidence_ref="ev-a", description="Approved dep",
            )
        ] if status == DetectionStatus.ADOPTED else [],
        reinvention_signals=[
            DetectionSignal(
                signal_id="sig-r", repo_id=repo_id,
                capability_id="platform_http_client",
                signal_type=SignalType.REINVENTION, weight=SignalWeight.HIGH,
                evidence_ref="ev-r", description="Custom class RetrySession",
            )
        ] if status == DetectionStatus.CUSTOM_IMPLEMENTATION else [],
    )


def _make_evidence(ev_id: str, repo_id: str) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=ev_id,
        scan_run_id="run-001",
        repo_id=repo_id,
        capability_id="platform_http_client",
        source_type="dependency",
        file_path="requirements.txt",
        content_summary=f"Evidence {ev_id}",
    )


class TestCrossRepoAggregator:
    def test_basic_metric_computation(self, aggregator, http_capability):
        results = [
            _make_result("payment-svc", "team-a", DetectionStatus.ADOPTED, ["ev-1"]),
            _make_result("reporting-svc", "team-b", DetectionStatus.CUSTOM_IMPLEMENTATION, ["ev-2"]),
            _make_result("recon-svc", "team-c", DetectionStatus.MISSING),
            _make_result("notif-svc", "team-d", DetectionStatus.NOT_ELIGIBLE),
        ]
        evidence = {
            "ev-1": _make_evidence("ev-1", "payment-svc"),
            "ev-2": _make_evidence("ev-2", "reporting-svc"),
        }
        metric, summary = aggregator.aggregate(results, http_capability, "batch-001", evidence)
        assert metric.adopted_count == 1
        assert metric.custom_implementation_count == 1
        assert metric.missing_count == 1
        assert metric.not_eligible_count == 1
        assert metric.eligible_repo_count == 3  # excludes NOT_ELIGIBLE
        assert metric.adoption_rate == pytest.approx(1 / 3, abs=0.01)

    def test_adoption_rate_excludes_exempt(self, aggregator, http_capability):
        results = [
            _make_result("svc-a", "team-a", DetectionStatus.ADOPTED),
            _make_result("svc-b", "team-b", DetectionStatus.EXEMPT),
            _make_result("svc-c", "team-c", DetectionStatus.MISSING),
        ]
        metric, _ = aggregator.aggregate(results, http_capability, "batch-001", {})
        assert metric.exempt_count == 1
        assert metric.eligible_repo_count == 2  # excludes EXEMPT
        assert metric.adoption_rate == pytest.approx(0.5, abs=0.01)

    def test_zero_eligible_repos(self, aggregator, http_capability):
        results = [
            _make_result("svc-a", "team-a", DetectionStatus.NOT_ELIGIBLE),
        ]
        metric, _ = aggregator.aggregate(results, http_capability, "batch-001", {})
        assert metric.eligible_repo_count == 0
        assert metric.adoption_rate == 0.0

    def test_summary_contains_all_repos(self, aggregator, http_capability):
        results = [
            _make_result("svc-a", "team-a", DetectionStatus.ADOPTED),
            _make_result("svc-b", "team-b", DetectionStatus.CUSTOM_IMPLEMENTATION),
        ]
        _, summary = aggregator.aggregate(results, http_capability, "batch-001", {})
        repo_ids = {r.repo_id for r in summary.repo_summaries}
        assert "svc-a" in repo_ids
        assert "svc-b" in repo_ids

    def test_summary_extracts_reinvention_patterns(self, aggregator, http_capability):
        results = [
            _make_result("svc-a", "team-a", DetectionStatus.CUSTOM_IMPLEMENTATION, ["ev-1"]),
        ]
        _, summary = aggregator.aggregate(results, http_capability, "batch-001", {})
        assert len(summary.common_reinvention_patterns) >= 1
        assert any("RetrySession" in p for p in summary.common_reinvention_patterns)

    def test_summary_evidence_items_selected(self, aggregator, http_capability):
        results = [
            _make_result("svc-a", "team-a", DetectionStatus.ADOPTED, ["ev-1"]),
        ]
        evidence = {"ev-1": _make_evidence("ev-1", "svc-a")}
        _, summary = aggregator.aggregate(results, http_capability, "batch-001", evidence)
        assert len(summary.evidence_items) >= 1

    def test_summary_includes_unknowns(self, aggregator, http_capability):
        result = _make_result("svc-a", "team-a", DetectionStatus.UNKNOWN)
        result.unknowns = ["Insufficient evidence"]
        _, summary = aggregator.aggregate([result], http_capability, "batch-001", {})
        assert any("svc-a" in u for u in summary.unknowns)

    def test_summary_capability_metadata(self, aggregator, http_capability):
        results = [_make_result("svc-a", "team-a", DetectionStatus.ADOPTED)]
        _, summary = aggregator.aggregate(results, http_capability, "batch-001", {})
        assert summary.capability_id == "platform_http_client"
        assert summary.capability_name == "Platform HTTP Client"

    def test_token_count_positive(self, aggregator, http_capability):
        results = [_make_result("svc-a", "team-a", DetectionStatus.ADOPTED, ["ev-1"])]
        evidence = {"ev-1": _make_evidence("ev-1", "svc-a")}
        _, summary = aggregator.aggregate(results, http_capability, "batch-001", evidence)
        assert summary.token_count >= 0

    def test_all_adopted(self, aggregator, http_capability):
        results = [
            _make_result(f"svc-{i}", f"team-{i}", DetectionStatus.ADOPTED)
            for i in range(3)
        ]
        metric, _ = aggregator.aggregate(results, http_capability, "batch-001", {})
        assert metric.adoption_rate == pytest.approx(1.0)
        assert metric.custom_implementation_count == 0
