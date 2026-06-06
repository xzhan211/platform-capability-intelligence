"""Shared pytest fixtures for platform-capability-intelligence tests."""
from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from platform_capability.models import (
    Capability, CapabilityCatalog, PlatformConventions,
    ApprovedUsagePatterns, AntiPatterns, EligibilityRules, EvidenceRules,
    MinimumEvidence, PatternRule, SignalWeight, CapabilityStatus,
    WorkspaceManifest, FileEntry,
)


# ---------------------------------------------------------------------------
# Capability / Catalog fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def http_capability() -> Capability:
    """A realistic platform_http_client capability for testing."""
    return Capability(
        capability_id="platform_http_client",
        name="Platform HTTP Client",
        category="integration",
        status=CapabilityStatus.STABLE,
        approved_usage_patterns=ApprovedUsagePatterns(
            dependencies=[
                PatternRule(pattern="platform-http-client", weight=SignalWeight.HIGH),
            ],
            imports=[
                PatternRule(pattern="platform_http_client.PlatformHttpClient", weight=SignalWeight.HIGH),
                PatternRule(pattern="platform_http_client", weight=SignalWeight.MEDIUM),
            ],
        ),
        anti_patterns=AntiPatterns(
            class_name_patterns=[
                PatternRule(pattern="RetrySession", weight=SignalWeight.HIGH),
                PatternRule(pattern="CustomRetry", weight=SignalWeight.MEDIUM),
            ],
            dependency_patterns=[
                PatternRule(pattern="requests", weight=SignalWeight.MEDIUM, note="raw requests"),
            ],
            code_patterns=[
                PatternRule(pattern="HTTPAdapter", weight=SignalWeight.HIGH, note="manual retry"),
                PatternRule(pattern="Retry(", weight=SignalWeight.HIGH, note="manual retry"),
            ],
        ),
        eligibility_rules=EligibilityRules(
            include_if_dependency=["requests", "httpx", "platform-http-client"],
            include_if_import_prefix=["requests", "httpx", "platform_http_client"],
        ),
        evidence_rules=EvidenceRules(collect_files=["requirements.txt", "*.py"]),
        minimum_evidence_required=MinimumEvidence(adoption=1, reinvention=1),
    )


@pytest.fixture
def minimal_catalog(http_capability) -> CapabilityCatalog:
    return CapabilityCatalog(
        catalog_version="1.0",
        platform_conventions=PlatformConventions(
            approved_import_prefixes=["platform_http_client", "platform_"],
            approved_dependency_prefixes=["platform-"],
        ),
        capabilities=[http_capability],
        exceptions=[],
    )


# ---------------------------------------------------------------------------
# Workspace fixture factory
# ---------------------------------------------------------------------------

@pytest.fixture
def make_workspace(tmp_path):
    """Factory: create a WorkspaceManifest backed by real files in tmp_path."""
    def _make(files: dict[str, str], repo_id: str = "test-repo") -> WorkspaceManifest:
        ws_dir = tmp_path / repo_id
        ws_dir.mkdir(parents=True, exist_ok=True)
        file_entries = []
        dep_files = []
        source_files = []
        config_files = []

        dep_names = {"requirements.txt", "setup.py", "pyproject.toml", "setup.cfg"}
        config_exts = {".yaml", ".yml", ".env", ".ini", ".json", ".cfg"}

        for rel_path, content in files.items():
            abs_path = ws_dir / rel_path
            abs_path.parent.mkdir(parents=True, exist_ok=True)
            abs_path.write_text(content)

            ext = abs_path.suffix.lower()
            lang = "python" if ext == ".py" else ""
            entry = FileEntry(
                file_id=rel_path[:12].replace("/", "_"),
                relative_path=rel_path,
                absolute_path=str(abs_path),
                extension=ext,
                size_bytes=len(content),
                language=lang,
            )
            file_entries.append(entry)
            name = abs_path.name
            if name in dep_names:
                dep_files.append(rel_path)
            elif ext in config_exts:
                config_files.append(rel_path)
            elif lang:
                source_files.append(rel_path)

        return WorkspaceManifest(
            workspace_id="ws-test",
            repo_id=repo_id,
            workspace_path=str(ws_dir),
            detected_languages=["python"] if any(f.endswith(".py") for f in files) else [],
            file_tree=file_entries,
            dependency_files=dep_files,
            config_files=config_files,
            source_files=source_files,
        )
    return _make


# ---------------------------------------------------------------------------
# Zip archive factory
# ---------------------------------------------------------------------------

@pytest.fixture
def make_zip(tmp_path):
    """Factory: create a zip archive at tmp_path/name.zip containing given files."""
    def _make(name: str, files: dict[str, str]) -> str:
        zip_path = tmp_path / f"{name}.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            for rel, content in files.items():
                zf.writestr(rel, content)
        return str(zip_path)
    return _make


# ---------------------------------------------------------------------------
# Minimal YAML strings
# ---------------------------------------------------------------------------

MINIMAL_CATALOG_YAML = """
catalog_version: "1.0"
owner: platform-team

platform_conventions:
  python:
    approved_import_prefixes:
      - "platform_"
    approved_dependency_prefixes:
      - "platform-"

capabilities:
  - capability_id: platform_http_client
    name: Platform HTTP Client
    status: stable
    approved_usage_patterns:
      dependencies:
        - pattern: "platform-http-client"
          weight: high
      imports:
        - pattern: "platform_http_client"
          weight: high
    anti_patterns:
      class_name_patterns:
        - pattern: "RetrySession"
          weight: high
      dependency_patterns:
        - pattern: "requests"
          weight: medium
          note: "raw requests"
      code_patterns:
        - pattern: "HTTPAdapter"
          weight: high
          note: "manual retry"
    eligibility_rules:
      include_if_dependency:
        - "requests"
        - "platform-http-client"
      include_if_import_prefix:
        - "requests"
        - "platform_http_client"
    minimum_evidence_required:
      adoption: 1
      reinvention: 1

exceptions: []
"""

MINIMAL_MANIFEST_YAML = """
scan_batch_id: test-batch-001
scan_timestamp: "2026-06-06T00:00:00Z"
catalog_version: "1.0"
repos:
  - repo_id: test-repo
    repo_name: test-repo
    tenant_id: test-team
    archive: {archive_path}
    branch: main
"""
