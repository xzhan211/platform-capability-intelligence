from __future__ import annotations

import uuid
from datetime import datetime, timezone

from platform_capability.models import (
    Capability, CapabilityDetectionResult, CapabilityCatalog,
    DetectionSignal, EvidenceItem, WorkspaceManifest,
    DetectionStatus, Confidence, SignalType, SignalWeight,
)


def _high_weight_count(signals: list[DetectionSignal], signal_type: SignalType) -> int:
    return sum(
        1 for s in signals
        if s.signal_type == signal_type and s.weight == SignalWeight.HIGH
    )


def _medium_weight_count(signals: list[DetectionSignal], signal_type: SignalType) -> int:
    return sum(
        1 for s in signals
        if s.signal_type == signal_type and s.weight == SignalWeight.MEDIUM
    )


def _is_eligible(workspace: WorkspaceManifest, capability: Capability) -> bool:
    rules = capability.eligibility_rules

    # Check dependency files
    dep_content = ""
    from pathlib import Path
    for rel in workspace.dependency_files:
        try:
            dep_content += (Path(workspace.workspace_path) / rel).read_text(errors="ignore").lower()
        except Exception:
            pass

    for dep in rules.include_if_dependency:
        if dep.lower() in dep_content:
            return True

    # Check imports in source files
    for rel in workspace.source_files:
        if not rel.endswith(".py"):
            continue
        try:
            content = (Path(workspace.workspace_path) / rel).read_text(errors="ignore")
        except Exception:
            continue
        for prefix in rules.include_if_import_prefix:
            if prefix.lower() in content.lower():
                return True

    # Check config files
    cfg_content = ""
    for rel in workspace.config_files:
        try:
            cfg_content += (Path(workspace.workspace_path) / rel).read_text(errors="ignore").lower()
        except Exception:
            pass
    for prefix in rules.include_if_config_key_prefix:
        if prefix.lower() in cfg_content:
            return True

    return False


class CapabilityUsageClassifier:
    def classify(
        self,
        workspace: WorkspaceManifest,
        capability: Capability,
        signals: list[DetectionSignal],
        items: list[EvidenceItem],
        catalog: CapabilityCatalog,
        scan_run_id: str,
    ) -> CapabilityDetectionResult:

        evidence_refs = [item.evidence_id for item in items]
        detection_id = f"det-{uuid.uuid4().hex[:12]}"

        # Check EXEMPT
        for ex in catalog.exceptions:
            if ex.repo_id == workspace.repo_id and ex.capability_id == capability.capability_id:
                if ex.expires is None or ex.expires >= datetime.now(timezone.utc).isoformat()[:10]:
                    return CapabilityDetectionResult(
                        detection_id=detection_id,
                        scan_run_id=scan_run_id,
                        repo_id=workspace.repo_id,
                        tenant_id="",
                        capability_id=capability.capability_id,
                        status=DetectionStatus.EXEMPT,
                        confidence=Confidence.HIGH,
                        evidence_refs=evidence_refs,
                        exempt_reason=ex.reason,
                        adoption_signals=signals,
                        reinvention_signals=[],
                        catalog_version=catalog.catalog_version,
                    )

        # Check NOT_ELIGIBLE
        if not _is_eligible(workspace, capability):
            return CapabilityDetectionResult(
                detection_id=detection_id,
                scan_run_id=scan_run_id,
                repo_id=workspace.repo_id,
                tenant_id="",
                capability_id=capability.capability_id,
                status=DetectionStatus.NOT_ELIGIBLE,
                confidence=Confidence.HIGH,
                evidence_refs=[],
                adoption_signals=[],
                reinvention_signals=[],
                catalog_version=catalog.catalog_version,
            )

        adoption_signals = [s for s in signals if s.signal_type == SignalType.ADOPTION]
        reinvention_signals = [s for s in signals if s.signal_type == SignalType.REINVENTION]

        high_adopt = _high_weight_count(adoption_signals, SignalType.ADOPTION)
        med_adopt = _medium_weight_count(adoption_signals, SignalType.ADOPTION)
        high_reinv = _high_weight_count(reinvention_signals, SignalType.REINVENTION)
        med_reinv = _medium_weight_count(reinvention_signals, SignalType.REINVENTION)

        # ADOPTED: ≥1 high-weight adoption OR ≥2 medium-weight adoption
        if high_adopt >= 1 or med_adopt >= 2:
            confidence = Confidence.HIGH if high_adopt >= 1 else Confidence.MEDIUM
            return CapabilityDetectionResult(
                detection_id=detection_id,
                scan_run_id=scan_run_id,
                repo_id=workspace.repo_id,
                tenant_id="",
                capability_id=capability.capability_id,
                status=DetectionStatus.ADOPTED,
                confidence=confidence,
                evidence_refs=evidence_refs,
                adoption_signals=adoption_signals,
                reinvention_signals=reinvention_signals,
                catalog_version=catalog.catalog_version,
            )

        # CUSTOM_IMPLEMENTATION: (≥1 high-weight reinvention OR ≥2 medium reinvention) AND no high adoption
        if (high_reinv >= 1 or med_reinv >= 2) and high_adopt == 0:
            confidence = Confidence.HIGH if high_reinv >= 1 else Confidence.MEDIUM
            return CapabilityDetectionResult(
                detection_id=detection_id,
                scan_run_id=scan_run_id,
                repo_id=workspace.repo_id,
                tenant_id="",
                capability_id=capability.capability_id,
                status=DetectionStatus.CUSTOM_IMPLEMENTATION,
                confidence=confidence,
                evidence_refs=evidence_refs,
                adoption_signals=adoption_signals,
                reinvention_signals=reinvention_signals,
                catalog_version=catalog.catalog_version,
            )

        # MISSING: eligible, no adoption, reinvention below threshold
        if not adoption_signals and high_reinv == 0 and med_reinv < 2:
            unknowns = ["No approved capability usage detected"]
            if reinvention_signals:
                unknowns.append(f"Weak reinvention signals detected ({len(reinvention_signals)} signal(s))")
            return CapabilityDetectionResult(
                detection_id=detection_id,
                scan_run_id=scan_run_id,
                repo_id=workspace.repo_id,
                tenant_id="",
                capability_id=capability.capability_id,
                status=DetectionStatus.MISSING,
                confidence=Confidence.MEDIUM,
                evidence_refs=evidence_refs,
                unknowns=unknowns,
                adoption_signals=[],
                reinvention_signals=reinvention_signals,
                catalog_version=catalog.catalog_version,
            )

        # UNKNOWN: insufficient evidence
        return CapabilityDetectionResult(
            detection_id=detection_id,
            scan_run_id=scan_run_id,
            repo_id=workspace.repo_id,
            tenant_id="",
            capability_id=capability.capability_id,
            status=DetectionStatus.UNKNOWN,
            confidence=Confidence.LOW,
            evidence_refs=evidence_refs,
            unknowns=["Insufficient evidence to classify"],
            adoption_signals=adoption_signals,
            reinvention_signals=reinvention_signals,
            catalog_version=catalog.catalog_version,
        )
