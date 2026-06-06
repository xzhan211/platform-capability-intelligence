"""Tests for classification/classifier.py — all 6 status paths."""
import pytest
from platform_capability.classification.classifier import CapabilityUsageClassifier
from platform_capability.models import (
    DetectionSignal, EvidenceItem, DetectionStatus, Confidence,
    SignalType, SignalWeight, CapabilityException,
)


@pytest.fixture
def classifier():
    return CapabilityUsageClassifier()


def _make_signal(signal_type: SignalType, weight: SignalWeight, repo_id="test-repo") -> DetectionSignal:
    from uuid import uuid4
    ev_id = f"ev-{uuid4().hex[:8]}"
    return DetectionSignal(
        signal_id=f"sig-{uuid4().hex[:8]}",
        repo_id=repo_id,
        capability_id="platform_http_client",
        signal_type=signal_type,
        weight=weight,
        evidence_ref=ev_id,
        description="test signal",
    )


def _make_evidence(ev_id: str, repo_id="test-repo") -> EvidenceItem:
    return EvidenceItem(
        evidence_id=ev_id,
        scan_run_id="run-001",
        repo_id=repo_id,
        capability_id="platform_http_client",
        source_type="dependency",
        file_path="requirements.txt",
        content_summary="test evidence",
    )


# ── ADOPTED ──────────────────────────────────────────────────────────────────

def test_adopted_high_weight(classifier, make_workspace, http_capability, minimal_catalog):
    ws = make_workspace({"requirements.txt": "platform-http-client==2.1.0\n"})
    sig = _make_signal(SignalType.ADOPTION, SignalWeight.HIGH)
    ev = _make_evidence(sig.evidence_ref)
    result = classifier.classify(ws, http_capability, [sig], [ev], minimal_catalog, "run-001")
    assert result.status == DetectionStatus.ADOPTED
    assert result.confidence == Confidence.HIGH


def test_adopted_two_medium_weight(classifier, make_workspace, http_capability, minimal_catalog):
    ws = make_workspace({"requirements.txt": "platform-http-client==2.1.0\n"})
    sig1 = _make_signal(SignalType.ADOPTION, SignalWeight.MEDIUM)
    sig2 = _make_signal(SignalType.ADOPTION, SignalWeight.MEDIUM)
    ev1 = _make_evidence(sig1.evidence_ref)
    ev2 = _make_evidence(sig2.evidence_ref)
    result = classifier.classify(ws, http_capability, [sig1, sig2], [ev1, ev2], minimal_catalog, "run-001")
    assert result.status == DetectionStatus.ADOPTED
    assert result.confidence == Confidence.MEDIUM


# ── CUSTOM_IMPLEMENTATION ─────────────────────────────────────────────────────

def test_custom_impl_high_weight_reinvention(classifier, make_workspace, http_capability, minimal_catalog):
    ws = make_workspace({"requirements.txt": "requests==2.31.0\n"})
    sig = _make_signal(SignalType.REINVENTION, SignalWeight.HIGH)
    ev = _make_evidence(sig.evidence_ref)
    result = classifier.classify(ws, http_capability, [sig], [ev], minimal_catalog, "run-001")
    assert result.status == DetectionStatus.CUSTOM_IMPLEMENTATION
    assert result.confidence == Confidence.HIGH


def test_custom_impl_two_medium_reinvention(classifier, make_workspace, http_capability, minimal_catalog):
    ws = make_workspace({"requirements.txt": "requests==2.31.0\n"})
    sig1 = _make_signal(SignalType.REINVENTION, SignalWeight.MEDIUM)
    sig2 = _make_signal(SignalType.REINVENTION, SignalWeight.MEDIUM)
    ev1 = _make_evidence(sig1.evidence_ref)
    ev2 = _make_evidence(sig2.evidence_ref)
    result = classifier.classify(ws, http_capability, [sig1, sig2], [ev1, ev2], minimal_catalog, "run-001")
    assert result.status == DetectionStatus.CUSTOM_IMPLEMENTATION
    assert result.confidence == Confidence.MEDIUM


def test_adoption_overrides_reinvention(classifier, make_workspace, http_capability, minimal_catalog):
    """High adoption signal beats any reinvention signals."""
    ws = make_workspace({"requirements.txt": "platform-http-client==2.1.0\nrequests==2.31.0\n"})
    adopt_sig = _make_signal(SignalType.ADOPTION, SignalWeight.HIGH)
    reinv_sig = _make_signal(SignalType.REINVENTION, SignalWeight.HIGH)
    ev1 = _make_evidence(adopt_sig.evidence_ref)
    ev2 = _make_evidence(reinv_sig.evidence_ref)
    result = classifier.classify(ws, http_capability, [adopt_sig, reinv_sig], [ev1, ev2], minimal_catalog, "run-001")
    assert result.status == DetectionStatus.ADOPTED


# ── MISSING ───────────────────────────────────────────────────────────────────

def test_missing_eligible_no_signals(classifier, make_workspace, http_capability, minimal_catalog):
    """Eligible repo with no signals → MISSING."""
    ws = make_workspace({"requirements.txt": "requests==2.31.0\n"})
    result = classifier.classify(ws, http_capability, [], [], minimal_catalog, "run-001")
    assert result.status == DetectionStatus.MISSING
    assert "No approved capability usage detected" in result.unknowns


def test_missing_weak_reinvention(classifier, make_workspace, http_capability, minimal_catalog):
    """One medium reinvention signal alone is not enough → MISSING."""
    ws = make_workspace({"requirements.txt": "requests==2.31.0\n"})
    sig = _make_signal(SignalType.REINVENTION, SignalWeight.MEDIUM)
    ev = _make_evidence(sig.evidence_ref)
    result = classifier.classify(ws, http_capability, [sig], [ev], minimal_catalog, "run-001")
    assert result.status == DetectionStatus.MISSING


# ── NOT_ELIGIBLE ──────────────────────────────────────────────────────────────

def test_not_eligible_no_http_deps(classifier, make_workspace, http_capability, minimal_catalog):
    """Repo with no HTTP-related dependencies is not eligible."""
    ws = make_workspace({"requirements.txt": "boto3==1.28.0\njinja2==3.1.2\n"})
    result = classifier.classify(ws, http_capability, [], [], minimal_catalog, "run-001")
    assert result.status == DetectionStatus.NOT_ELIGIBLE
    assert result.confidence == Confidence.HIGH


# ── EXEMPT ────────────────────────────────────────────────────────────────────

def test_exempt_status(classifier, make_workspace, http_capability, minimal_catalog):
    """Repo with a valid exception → EXEMPT."""
    from platform_capability.models import CapabilityCatalog, PlatformConventions
    catalog = CapabilityCatalog(
        catalog_version="1.0",
        platform_conventions=PlatformConventions(),
        capabilities=[http_capability],
        exceptions=[CapabilityException(
            repo_id="test-repo",
            capability_id="platform_http_client",
            reason="Legacy service",
            approved_by="platform-team",
            approved_at="2026-01-01",
            expires=None,
        )],
    )
    ws = make_workspace({"requirements.txt": "requests==2.31.0\n"})
    result = classifier.classify(ws, http_capability, [], [], catalog, "run-001")
    assert result.status == DetectionStatus.EXEMPT
    assert result.exempt_reason == "Legacy service"


def test_exempt_expired_treated_as_missing(classifier, make_workspace, http_capability, minimal_catalog):
    """Expired exception is ignored, repo classified normally."""
    from platform_capability.models import CapabilityCatalog, PlatformConventions
    catalog = CapabilityCatalog(
        catalog_version="1.0",
        platform_conventions=PlatformConventions(),
        capabilities=[http_capability],
        exceptions=[CapabilityException(
            repo_id="test-repo",
            capability_id="platform_http_client",
            reason="Expired exception",
            approved_by="platform-team",
            approved_at="2025-01-01",
            expires="2025-06-01",  # expired
        )],
    )
    ws = make_workspace({"requirements.txt": "requests==2.31.0\n"})
    result = classifier.classify(ws, http_capability, [], [], catalog, "run-001")
    assert result.status != DetectionStatus.EXEMPT


# ── Result fields ─────────────────────────────────────────────────────────────

def test_result_includes_evidence_refs(classifier, make_workspace, http_capability, minimal_catalog):
    ws = make_workspace({"requirements.txt": "platform-http-client==2.1.0\n"})
    sig = _make_signal(SignalType.ADOPTION, SignalWeight.HIGH)
    ev = _make_evidence(sig.evidence_ref)
    result = classifier.classify(ws, http_capability, [sig], [ev], minimal_catalog, "run-001")
    assert ev.evidence_id in result.evidence_refs


def test_result_catalog_version(classifier, make_workspace, http_capability, minimal_catalog):
    ws = make_workspace({"requirements.txt": "requests==2.31.0\n"})
    result = classifier.classify(ws, http_capability, [], [], minimal_catalog, "run-001")
    assert result.catalog_version == minimal_catalog.catalog_version


def test_not_eligible_has_empty_evidence(classifier, make_workspace, http_capability, minimal_catalog):
    ws = make_workspace({"requirements.txt": "boto3==1.28.0\n"})
    result = classifier.classify(ws, http_capability, [], [], minimal_catalog, "run-001")
    assert result.evidence_refs == []
