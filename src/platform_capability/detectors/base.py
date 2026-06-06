from __future__ import annotations

from abc import ABC, abstractmethod

from platform_capability.models import Capability, DetectionSignal, EvidenceItem, WorkspaceManifest


class Detector(ABC):
    """Language-agnostic detector interface."""

    @abstractmethod
    def detect(
        self,
        workspace: WorkspaceManifest,
        capability: Capability,
        scan_run_id: str,
    ) -> tuple[list[DetectionSignal], list[EvidenceItem]]:
        """Return (signals, evidence_items) for this capability in this workspace."""
