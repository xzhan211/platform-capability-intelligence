from __future__ import annotations

import re
import uuid
from pathlib import Path

from platform_capability.detectors.base import Detector
from platform_capability.models import (
    Capability, DetectionSignal, EvidenceItem,
    SignalType, SignalWeight, Confidence, WorkspaceManifest, PlatformConventions,
)

IMPORT_RE = re.compile(r"^\s*(?:from\s+([\w\.]+)|import\s+([\w\.]+))", re.MULTILINE)


class PlatformNamespaceDetector(Detector):
    """Tier 1: detects generic platform usage via namespace conventions."""

    def __init__(self, conventions: PlatformConventions):
        self._conventions = conventions

    def detect(self, workspace: WorkspaceManifest, capability: Capability, scan_run_id: str):
        signals: list[DetectionSignal] = []
        items: list[EvidenceItem] = []

        if not (
            self._conventions.approved_import_prefixes
            or self._conventions.approved_dependency_prefixes
        ):
            return signals, items

        # Check dependency files
        for rel_path in workspace.dependency_files:
            abs_path = Path(workspace.workspace_path) / rel_path
            try:
                content = abs_path.read_text(errors="ignore").lower()
            except Exception:
                continue
            for prefix in self._conventions.approved_dependency_prefixes:
                if prefix.lower() in content:
                    ev_id = f"ev-ns-dep-{uuid.uuid4().hex[:8]}"
                    items.append(EvidenceItem(
                        evidence_id=ev_id,
                        scan_run_id=scan_run_id,
                        repo_id=workspace.repo_id,
                        capability_id=capability.capability_id,
                        source_type="generic_platform",
                        file_path=rel_path,
                        content_summary=f"Platform namespace prefix '{prefix}' found in {Path(rel_path).name}",
                    ))
                    signals.append(DetectionSignal(
                        signal_id=f"sig-{ev_id}",
                        repo_id=workspace.repo_id,
                        capability_id=capability.capability_id,
                        signal_type=SignalType.GENERIC_PLATFORM,
                        weight=SignalWeight.MEDIUM,
                        evidence_ref=ev_id,
                        confidence=Confidence.MEDIUM,
                        description=f"Platform dependency prefix: {prefix}",
                    ))

        # Check source imports
        for rel_path in workspace.source_files:
            if not rel_path.endswith(".py"):
                continue
            abs_path = Path(workspace.workspace_path) / rel_path
            try:
                content = abs_path.read_text(errors="ignore")
            except Exception:
                continue
            for m in IMPORT_RE.finditer(content):
                mod = (m.group(1) or m.group(2) or "").strip()
                for prefix in self._conventions.approved_import_prefixes:
                    if mod.startswith(prefix):
                        ev_id = f"ev-ns-imp-{uuid.uuid4().hex[:8]}"
                        line_num = content[:m.start()].count("\n") + 1
                        items.append(EvidenceItem(
                            evidence_id=ev_id,
                            scan_run_id=scan_run_id,
                            repo_id=workspace.repo_id,
                            capability_id=capability.capability_id,
                            source_type="generic_platform",
                            file_path=rel_path,
                            line_start=line_num,
                            content_summary=f"Platform import '{mod}' matches prefix '{prefix}'",
                            raw_content=content.splitlines()[line_num - 1] if line_num <= len(content.splitlines()) else "",
                        ))
                        signals.append(DetectionSignal(
                            signal_id=f"sig-{ev_id}",
                            repo_id=workspace.repo_id,
                            capability_id=capability.capability_id,
                            signal_type=SignalType.GENERIC_PLATFORM,
                            weight=SignalWeight.MEDIUM,
                            evidence_ref=ev_id,
                            confidence=Confidence.MEDIUM,
                            description=f"Platform import prefix: {mod}",
                        ))
                        break

        return signals, items
