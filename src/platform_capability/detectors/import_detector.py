from __future__ import annotations

import re
import uuid
from pathlib import Path

from platform_capability.detectors.base import Detector
from platform_capability.models import (
    Capability, DetectionSignal, EvidenceItem,
    SignalType, SignalWeight, Confidence, WorkspaceManifest,
)

IMPORT_RE = re.compile(
    r"^\s*(?:from\s+([\w\.]+)\s+import\s+([\w\s,\*]+)|import\s+([\w\.]+))",
    re.MULTILINE,
)


def _extract_imports(content: str) -> list[tuple[str, list[str]]]:
    """Return list of (module, [imported_names]) tuples."""
    found = []
    for m in IMPORT_RE.finditer(content):
        if m.group(1):  # from X import Y, Z
            module = m.group(1).strip()
            names = [n.strip() for n in m.group(2).split(",") if n.strip()]
        else:  # import X
            module = m.group(3).strip()
            names = []
        found.append((module, names))
    return found


class ImportDetector(Detector):
    """Detects adoption/reinvention signals from Python import statements."""

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

            imports = _extract_imports(content)
            lines = content.splitlines()

            for imp, imported_names in imports:
                # Check adoption imports (module path)
                for pat in capability.approved_usage_patterns.imports:
                    pat_mod = pat.pattern.rstrip(".*")
                    if imp == pat_mod or imp.startswith(pat_mod + ".") or imp.startswith(pat_mod):
                        line_num = self._find_import_line(lines, imp)
                        ev_id = f"ev-imp-adopt-{uuid.uuid4().hex[:8]}"
                        snippet = self._get_snippet(lines, line_num, 3)
                        items.append(EvidenceItem(
                            evidence_id=ev_id,
                            scan_run_id=scan_run_id,
                            repo_id=workspace.repo_id,
                            capability_id=capability.capability_id,
                            source_type="import",
                            file_path=rel_path,
                            line_start=line_num,
                            line_end=line_num + 2,
                            content_summary=f"Approved import '{imp}' in {Path(rel_path).name}",
                            raw_content=snippet,
                        ))
                        signals.append(DetectionSignal(
                            signal_id=f"sig-{ev_id}",
                            repo_id=workspace.repo_id,
                            capability_id=capability.capability_id,
                            signal_type=SignalType.ADOPTION,
                            weight=pat.weight,
                            evidence_ref=ev_id,
                            confidence=Confidence.HIGH if pat.weight == SignalWeight.HIGH else Confidence.MEDIUM,
                            description=f"Approved import: {imp}",
                        ))

                # Check reinvention class name patterns against:
                #   (a) module path components, and
                #   (b) explicitly imported names (from X import Y)
                for pat in capability.anti_patterns.class_name_patterns:
                    pat_lower = pat.pattern.lower()
                    candidates = list(imp.replace(".", "_").split("_")) + imported_names
                    if any(
                        self._matches_pattern(part, pat_lower)
                        for part in candidates
                        if part
                    ):
                        line_num = self._find_import_line(lines, imp)
                        ev_id = f"ev-imp-reinv-{uuid.uuid4().hex[:8]}"
                        snippet = self._get_snippet(lines, line_num, 3)
                        display = f"{imp}" + (f" import {', '.join(imported_names)}" if imported_names else "")
                        items.append(EvidenceItem(
                            evidence_id=ev_id,
                            scan_run_id=scan_run_id,
                            repo_id=workspace.repo_id,
                            capability_id=capability.capability_id,
                            source_type="import",
                            file_path=rel_path,
                            line_start=line_num,
                            content_summary=f"Suspicious import '{display}' matches anti-pattern '{pat.pattern}'",
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
                            description=f"Suspicious import: {display}",
                        ))

        return signals, items

    @staticmethod
    def _find_import_line(lines: list[str], module: str) -> int:
        for i, line in enumerate(lines, 1):
            if module in line and ("import" in line):
                return i
        return 1

    @staticmethod
    def _get_snippet(lines: list[str], line_num: int, context: int = 3) -> str:
        start = max(0, line_num - 1)
        end = min(len(lines), line_num + context)
        return "\n".join(lines[start:end])

    @staticmethod
    def _matches_pattern(text: str, pattern: str) -> bool:
        import fnmatch
        text_l = text.lower()
        pat_clean = pattern.strip("*").lower()
        if not pat_clean:
            return False
        return pat_clean in text_l or fnmatch.fnmatch(text_l, pattern.lower())
