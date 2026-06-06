"""Tests for domain models serialization and validation."""
import pytest
from platform_capability.models import (
    Capability, CapabilityCatalog, CapabilityDetectionResult,
    CrossRepoMetric, CrossRepoEvidenceSummary, DetectionStatus, Confidence,
    EvidenceItem, DetectionSignal, SignalType, SignalWeight,
    FinalReport, EvaluationResult, EvaluationFinalStatus,
    LLMUsageMetadata, SignalSummarizerOutput, InsightGeneratorOutput,
    LLMRecommendation, RepoSummaryForLLM, WorkspaceManifest, FileEntry,
    CapabilityStatus, PatternRule,
)


def test_capability_defaults():
    cap = Capability(capability_id="test", name="Test")
    assert cap.status == CapabilityStatus.STABLE
    assert cap.approved_usage_patterns.dependencies == []
    assert cap.anti_patterns.class_name_patterns == []
    assert cap.eligibility_rules.include_if_dependency == []


def test_capability_roundtrip():
    cap = Capability(
        capability_id="platform_http_client",
        name="Platform HTTP Client",
        status=CapabilityStatus.BETA,
    )
    data = cap.model_dump()
    restored = Capability(**data)
    assert restored.capability_id == cap.capability_id
    assert restored.status == CapabilityStatus.BETA


def test_detection_result_serialization():
    result = CapabilityDetectionResult(
        detection_id="det-001",
        scan_run_id="run-001",
        repo_id="payment-service",
        tenant_id="payments-team",
        capability_id="platform_http_client",
        status=DetectionStatus.ADOPTED,
        confidence=Confidence.HIGH,
        evidence_refs=["ev-001", "ev-002"],
    )
    data = result.model_dump()
    assert data["status"] == "ADOPTED"
    assert data["confidence"] == "high"
    assert len(data["evidence_refs"]) == 2


def test_detection_status_enum_values():
    assert DetectionStatus.ADOPTED == "ADOPTED"
    assert DetectionStatus.CUSTOM_IMPLEMENTATION == "CUSTOM_IMPLEMENTATION"
    assert DetectionStatus.MISSING == "MISSING"
    assert DetectionStatus.NOT_ELIGIBLE == "NOT_ELIGIBLE"
    assert DetectionStatus.UNKNOWN == "UNKNOWN"
    assert DetectionStatus.EXEMPT == "EXEMPT"


def test_cross_repo_metric():
    m = CrossRepoMetric(
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
    assert m.adoption_rate == 0.25
    assert m.eligible_repo_count == 4


def test_evidence_item_optional_fields():
    item = EvidenceItem(
        evidence_id="ev-001",
        scan_run_id="run-001",
        repo_id="test-repo",
        capability_id="platform_http_client",
        source_type="dependency",
        file_path="requirements.txt",
        content_summary="Found platform-http-client",
    )
    assert item.line_start is None
    assert item.raw_content == ""


def test_detection_signal_defaults():
    sig = DetectionSignal(
        signal_id="sig-001",
        repo_id="test-repo",
        capability_id="platform_http_client",
        signal_type=SignalType.ADOPTION,
        weight=SignalWeight.HIGH,
        evidence_ref="ev-001",
    )
    assert sig.confidence == Confidence.MEDIUM
    assert sig.description == ""


def test_evaluation_result_defaults():
    ev = EvaluationResult(
        evaluation_id="eval-001",
        scan_batch_id="batch-001",
    )
    assert ev.final_status == EvaluationFinalStatus.ACCEPTED
    assert ev.hallucination_count == 0
    assert ev.failure_reasons == []


def test_final_report_serialization(http_capability, minimal_catalog):
    from datetime import datetime, timezone
    report = FinalReport(
        report_id="report-001",
        scan_batch_id="batch-001",
        catalog_version="1.0",
        generated_at=datetime.now(timezone.utc).isoformat(),
        detection_results=[],
        metrics=[],
    )
    data = report.model_dump()
    assert data["report_id"] == "report-001"
    assert data["detection_results"] == []


def test_workspace_manifest():
    wm = WorkspaceManifest(
        workspace_id="ws-001",
        repo_id="test-repo",
        workspace_path="/tmp/test",
        detected_languages=["python"],
        file_tree=[],
        dependency_files=["requirements.txt"],
        config_files=[],
        source_files=["src/main.py"],
    )
    assert "python" in wm.detected_languages
    assert len(wm.dependency_files) == 1


def test_llm_recommendation():
    rec = LLMRecommendation(
        recommendation_id="rec-001",
        priority="high",
        target="reporting-service",
        action="Migrate to platform client",
        evidence_refs=["ev-001"],
    )
    assert rec.priority == "high"
    assert rec.evidence_refs == ["ev-001"]


def test_pattern_rule_defaults():
    pr = PatternRule(pattern="requests")
    assert pr.weight == SignalWeight.MEDIUM
    assert pr.note == ""
