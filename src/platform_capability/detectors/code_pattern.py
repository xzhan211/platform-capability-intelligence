from __future__ import annotations

import fnmatch
import re
import uuid
from pathlib import Path

from platform_capability.detectors.base import Detector
from platform_capability.models import (
    Capability, DetectionSignal, EvidenceItem,
    SignalType, SignalWeight, Confidence, WorkspaceManifest,
)

CLASS_RE = re.compile(r"^\s*class\s+(\w+)", re.MULTILINE)
FUNC_RE = re.compile(r"^\s*def\s+(\w+)", re.MULTILINE)


class CodePatternDetector(Detector):
    """Detects reinvention signals from class/function names in source files."""

    def detect(self, workspace: WorkspaceManifest, capability: Capability, scan_run_id: str):
        signals: list[DetectionSignal] = []
        items: list[EvidenceItem] = []

        for rel_path in workspace.source_files:
            if not rel_path.endswith(".py"):
                continue
            abs_path = Path(workspace.workspace_path) / rel_path
            try:
                content = abs_path.read_text(errors="ignore")
            except Exception:
                continue

            lines = content.splitlines()

            # Check class names
            for m in CLASS_RE.finditer(content):
                class_name = m.group(1)
                for pat in capability.anti_patterns.class_name_patterns:
                    if fnmatch.fnmatch(class_name.lower(), pat.pattern.lower().strip("*") + "*") or \
                       fnmatch.fnmatch(class_name.lower(), "*" + pat.pattern.lower().strip("*") + "*") or \
                       pat.pattern.lower().strip("*") in class_name.lower():
                        line_num = content[:m.start()].count("\n") + 1
                        ev_id = f"ev-cls-{uuid.uuid4().hex[:8]}"
                        snippet = self._get_snippet(lines, line_num, 5)
                        items.append(EvidenceItem(
                            evidence_id=ev_id,
                            scan_run_id=scan_run_id,
                            repo_id=workspace.repo_id,
                            capability_id=capability.capability_id,
                            source_type="code_snippet",
                            file_path=rel_path,
                            line_start=line_num,
                            line_end=line_num + 5,
                            content_summary=f"Custom class '{class_name}' matches anti-pattern '{pat.pattern}' in {Path(rel_path).name}",
                            raw_content=snippet,
                        ))
                        signals.append(DetectionSignal(
                            signal_id=f"sig-{ev_id}",
                            repo_id=workspace.repo_id,
                            capability_id=capability.capability_id,
                            signal_type=SignalType.REINVENTION,
                            weight=pat.weight,
                            evidence_ref=ev_id,
                            confidence=Confidence.HIGH if pat.weight == SignalWeight.HIGH else Confidence.MEDIUM,
                            description=f"Custom class: {class_name} (matches: {pat.pattern})",
                        ))

            # Check code patterns (inline patterns in source)
            for pat in capability.anti_patterns.code_patterns:
                pat_str = pat.pattern.lower()
                for i, line in enumerate(lines, 1):
                    if pat_str in line.lower():
                        ev_id = f"ev-code-{uuid.uuid4().hex[:8]}"
                        snippet = self._get_snippet(lines, i, 3)
                        items.append(EvidenceItem(
                            evidence_id=ev_id,
                            scan_run_id=scan_run_id,
                            repo_id=workspace.repo_id,
                            capability_id=capability.capability_id,
                            source_type="code_snippet",
                            file_path=rel_path,
                            line_start=i,
                            line_end=i + 3,
                            content_summary=f"Code pattern '{pat.pattern}' found in {Path(rel_path).name}:{i}",
                            raw_content=snippet,
                        ))
                        signals.append(DetectionSignal(
                            signal_id=f"sig-{ev_id}",
                            repo_id=workspace.repo_id,
                            capability_id=capability.capability_id,
                            signal_type=SignalType.REINVENTION,
                            weight=pat.weight,
                            evidence_ref=ev_id,
                            confidence=Confidence.MEDIUM,
                            description=f"Code pattern: {pat.pattern} ({pat.note})",
                        ))
                        break  # one signal per pattern per file is enough

        return signals, items

    @staticmethod
    def _get_snippet(lines: list[str], line_num: int, context: int = 5) -> str:
        start = max(0, line_num - 1)
        end = min(len(lines), line_num + context)
        return "\n".join(f"{start + i + 1}: {l}" for i, l in enumerate(lines[start:end]))
