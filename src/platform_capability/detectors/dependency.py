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


def _normalize_dep(dep_line: str) -> str:
    """Strip version specifiers and extras from a pip requirement line."""
    dep_line = dep_line.strip()
    if dep_line.startswith(("#", "-", ".", "git+")):
        return ""
    name = re.split(r"[>=<!;\[\s]", dep_line)[0].strip().lower().replace("_", "-")
    return name


class DependencyDetector(Detector):
    """Detects adoption/reinvention signals in dependency files."""

    DEP_PARSERS = {
        "requirements.txt": "_parse_pip",
        "setup.py": "_parse_setup_py",
        "pyproject.toml": "_parse_pyproject",
        "setup.cfg": "_parse_setup_cfg",
        "pom.xml": "_parse_pom",
        "build.gradle": "_parse_gradle",
        "build.gradle.kts": "_parse_gradle",
    }

    def detect(self, workspace: WorkspaceManifest, capability: Capability, scan_run_id: str):
        signals: list[DetectionSignal] = []
        items: list[EvidenceItem] = []

        for rel_path in workspace.dependency_files:
            fname = Path(rel_path).name
            parser_name = self.DEP_PARSERS.get(fname)
            if not parser_name:
                continue
            abs_path = Path(workspace.workspace_path) / rel_path
            try:
                deps = getattr(self, parser_name)(abs_path)
            except Exception:
                continue

            for dep_name in deps:
                if not dep_name:
                    continue
                # Check adoption patterns
                for pat in capability.approved_usage_patterns.dependencies:
                    if fnmatch.fnmatch(dep_name, pat.pattern.lower().replace("_", "-")):
                        ev_id = f"ev-dep-adopt-{uuid.uuid4().hex[:8]}"
                        items.append(EvidenceItem(
                            evidence_id=ev_id,
                            scan_run_id=scan_run_id,
                            repo_id=workspace.repo_id,
                            capability_id=capability.capability_id,
                            source_type="dependency",
                            file_path=rel_path,
                            content_summary=f"Approved dependency '{dep_name}' found in {fname}",
                            raw_content=dep_name,
                        ))
                        signals.append(DetectionSignal(
                            signal_id=f"sig-{ev_id}",
                            repo_id=workspace.repo_id,
                            capability_id=capability.capability_id,
                            signal_type=SignalType.ADOPTION,
                            weight=pat.weight,
                            evidence_ref=ev_id,
                            confidence=Confidence.HIGH if pat.weight == SignalWeight.HIGH else Confidence.MEDIUM,
                            description=f"Approved dependency: {dep_name}",
                        ))

                # Check reinvention patterns
                for pat in capability.anti_patterns.dependency_patterns:
                    pat_lower = pat.pattern.lower().replace("_", "-")
                    if fnmatch.fnmatch(dep_name, pat_lower) or dep_name in pat_lower:
                        ev_id = f"ev-dep-reinv-{uuid.uuid4().hex[:8]}"
                        items.append(EvidenceItem(
                            evidence_id=ev_id,
                            scan_run_id=scan_run_id,
                            repo_id=workspace.repo_id,
                            capability_id=capability.capability_id,
                            source_type="dependency",
                            file_path=rel_path,
                            content_summary=f"Reinvention dependency '{dep_name}' found in {fname}: {pat.note}",
                            raw_content=dep_name,
                        ))
                        signals.append(DetectionSignal(
                            signal_id=f"sig-{ev_id}",
                            repo_id=workspace.repo_id,
                            capability_id=capability.capability_id,
                            signal_type=SignalType.REINVENTION,
                            weight=pat.weight,
                            evidence_ref=ev_id,
                            confidence=Confidence.HIGH if pat.weight == SignalWeight.HIGH else Confidence.MEDIUM,
                            description=f"Reinvention dependency: {dep_name} ({pat.note})",
                        ))

        return signals, items

    def _parse_pip(self, path: Path) -> list[str]:
        deps = []
        for line in path.read_text(errors="ignore").splitlines():
            name = _normalize_dep(line)
            if name:
                deps.append(name)
        return deps

    def _parse_pyproject(self, path: Path) -> list[str]:
        content = path.read_text(errors="ignore")
        # Simple regex extraction from [project] dependencies
        deps = []
        in_deps = False
        for line in content.splitlines():
            stripped = line.strip()
            if stripped in ("[project.dependencies]", "dependencies = [") or stripped.startswith("dependencies"):
                in_deps = True
            if in_deps:
                name = _normalize_dep(stripped.strip('",\''))
                if name and not name.startswith("["):
                    deps.append(name)
                if stripped == "]":
                    in_deps = False
        # Also try simple line matching
        for match in re.finditer(r'"([a-zA-Z0-9_\-]+)[\s>=<!\[]', content):
            name = match.group(1).lower().replace("_", "-")
            if name:
                deps.append(name)
        return list(set(deps))

    def _parse_setup_py(self, path: Path) -> list[str]:
        content = path.read_text(errors="ignore")
        deps = []
        for match in re.finditer(r'["\']([a-zA-Z0-9_\-]+)[>=<!\s"\']', content):
            name = match.group(1).lower().replace("_", "-")
            if len(name) > 2:
                deps.append(name)
        return deps

    def _parse_setup_cfg(self, path: Path) -> list[str]:
        content = path.read_text(errors="ignore")
        deps = []
        in_install = False
        for line in content.splitlines():
            stripped = line.strip()
            if stripped in ("install_requires =", "install_requires="):
                in_install = True
                continue
            if in_install:
                if stripped.startswith("[") or (stripped and not stripped[0].isspace() and "=" in stripped):
                    in_install = False
                    continue
                name = _normalize_dep(stripped)
                if name:
                    deps.append(name)
        return deps

    def _parse_pom(self, path: Path) -> list[str]:
        content = path.read_text(errors="ignore")
        return re.findall(r"<artifactId>([a-zA-Z0-9\-_\.]+)</artifactId>", content)

    def _parse_gradle(self, path: Path) -> list[str]:
        content = path.read_text(errors="ignore")
        deps = []
        for match in re.finditer(r'["\']([a-zA-Z0-9\.\-_]+):([a-zA-Z0-9\.\-_]+)', content):
            deps.append(match.group(2).lower())
        return deps
