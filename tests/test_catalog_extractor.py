"""Tests for catalog/extractor.py and load_catalog() auto-detection."""
from __future__ import annotations

import zipfile
from pathlib import Path

import pytest
import yaml

from platform_capability.catalog.extractor import (
    _parse_exports,
    _parse_pyproject,
    _humanize,
    extract_catalog_from_platform_manifest,
)
from platform_capability.catalog.loader import load_catalog
from platform_capability.models import CapabilityStatus, SignalWeight


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PYPROJECT_TOML = """\
[project]
name = "platform-http-client"
version = "2.1.0"
description = "Standard platform HTTP client with retry and observability."

[tool.platform]
category = "integration"
owner_team = "platform-core"
documentation_url = "https://internal/docs/platform-http-client"
recommended_for = ["services that call HTTP APIs"]
"""

INIT_WITH_ALL = """\
from platform_http_client.client import PlatformHttpClient, HttpClientConfig

__all__ = ["PlatformHttpClient", "HttpClientConfig"]
"""

INIT_WITHOUT_ALL = """\
class PlatformHttpClient:
    pass

class HttpClientConfig:
    pass

def _internal_helper():
    pass
"""

SETUP_PY = """\
from setuptools import setup

setup(
    name="platform-auth-client",
    version="1.0.0",
    description="Auth wrapper",
)
"""


def _make_platform_zip(tmp_path: Path, files: dict[str, str], name: str = "platform-http-client") -> Path:
    zip_path = tmp_path / f"{name}.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        for rel, content in files.items():
            zf.writestr(f"{name}/{rel}", content)
    return zip_path


# ---------------------------------------------------------------------------
# _humanize
# ---------------------------------------------------------------------------

def test_humanize_hyphenated():
    assert _humanize("platform-http-client") == "Platform Http Client"


def test_humanize_single_word():
    assert _humanize("platform") == "Platform"


# ---------------------------------------------------------------------------
# _parse_pyproject
# ---------------------------------------------------------------------------

def test_parse_pyproject_reads_name_version_description(tmp_path):
    (tmp_path / "pyproject.toml").write_text(PYPROJECT_TOML)
    result = _parse_pyproject(tmp_path)
    assert result["name"] == "platform-http-client"
    assert result["version"] == "2.1.0"
    assert "retry" in result["description"]


def test_parse_pyproject_reads_tool_platform_section(tmp_path):
    (tmp_path / "pyproject.toml").write_text(PYPROJECT_TOML)
    result = _parse_pyproject(tmp_path)
    assert result["tool_platform"]["category"] == "integration"
    assert result["tool_platform"]["owner_team"] == "platform-core"
    assert result["tool_platform"]["documentation_url"] == "https://internal/docs/platform-http-client"


def test_parse_pyproject_fallback_to_setup_py(tmp_path):
    (tmp_path / "setup.py").write_text(SETUP_PY)
    result = _parse_pyproject(tmp_path)
    assert result["name"] == "platform-auth-client"
    assert result["version"] == "1.0.0"


def test_parse_pyproject_no_files_uses_dir_name(tmp_path):
    result = _parse_pyproject(tmp_path)
    assert result["name"] == tmp_path.name
    assert result["version"] == ""


# ---------------------------------------------------------------------------
# _parse_exports
# ---------------------------------------------------------------------------

def test_parse_exports_reads_dunder_all(tmp_path):
    init = tmp_path / "src" / "platform_http_client" / "__init__.py"
    init.parent.mkdir(parents=True)
    init.write_text(INIT_WITH_ALL)
    exports = _parse_exports(tmp_path, "platform_http_client")
    assert exports == ["PlatformHttpClient", "HttpClientConfig"]


def test_parse_exports_fallback_to_class_names(tmp_path):
    init = tmp_path / "src" / "platform_http_client" / "__init__.py"
    init.parent.mkdir(parents=True)
    init.write_text(INIT_WITHOUT_ALL)
    exports = _parse_exports(tmp_path, "platform_http_client")
    assert "PlatformHttpClient" in exports
    assert "HttpClientConfig" in exports
    assert "_internal_helper" not in exports


def test_parse_exports_flat_module_layout(tmp_path):
    init = tmp_path / "platform_http_client" / "__init__.py"
    init.parent.mkdir(parents=True)
    init.write_text(INIT_WITH_ALL)
    exports = _parse_exports(tmp_path, "platform_http_client")
    assert exports == ["PlatformHttpClient", "HttpClientConfig"]


def test_parse_exports_missing_init_returns_empty(tmp_path):
    exports = _parse_exports(tmp_path, "platform_http_client")
    assert exports == []


# ---------------------------------------------------------------------------
# extract_catalog_from_platform_manifest (end-to-end)
# ---------------------------------------------------------------------------

@pytest.fixture
def platform_zip(tmp_path) -> Path:
    return _make_platform_zip(tmp_path, {
        "pyproject.toml": PYPROJECT_TOML,
        "src/platform_http_client/__init__.py": INIT_WITH_ALL,
    })


@pytest.fixture
def platform_manifest_file(tmp_path, platform_zip) -> Path:
    manifest = {
        "platform_manifest_version": "1.0",
        "owner": "platform-team",
        "platform_conventions": {
            "python": {
                "approved_import_prefixes": ["platform_"],
                "approved_dependency_prefixes": ["platform-"],
            },
            "config_key_prefixes": ["platform."],
        },
        "platform_repos": [
            {
                "repo_id": "platform-http-client",
                "archive": str(platform_zip),
                "owner_team": "platform-core",
                "category": "integration",
                "status": "stable",
            }
        ],
    }
    path = tmp_path / "platform_manifest.yaml"
    path.write_text(yaml.dump(manifest))
    return path


def test_extract_catalog_returns_one_capability(platform_manifest_file):
    raw = yaml.safe_load(platform_manifest_file.read_text())
    catalog = extract_catalog_from_platform_manifest(platform_manifest_file, raw)
    assert len(catalog.capabilities) == 1


def test_extract_catalog_capability_id(platform_manifest_file):
    raw = yaml.safe_load(platform_manifest_file.read_text())
    catalog = extract_catalog_from_platform_manifest(platform_manifest_file, raw)
    cap = catalog.capabilities[0]
    assert cap.capability_id == "platform_http_client"


def test_extract_catalog_capability_name_and_description(platform_manifest_file):
    raw = yaml.safe_load(platform_manifest_file.read_text())
    catalog = extract_catalog_from_platform_manifest(platform_manifest_file, raw)
    cap = catalog.capabilities[0]
    assert "Platform" in cap.name
    assert "retry" in cap.description.lower()


def test_extract_catalog_status_is_stable(platform_manifest_file):
    raw = yaml.safe_load(platform_manifest_file.read_text())
    catalog = extract_catalog_from_platform_manifest(platform_manifest_file, raw)
    assert catalog.capabilities[0].status == CapabilityStatus.STABLE


def test_extract_catalog_dependency_pattern(platform_manifest_file):
    raw = yaml.safe_load(platform_manifest_file.read_text())
    catalog = extract_catalog_from_platform_manifest(platform_manifest_file, raw)
    cap = catalog.capabilities[0]
    dep_patterns = [p.pattern for p in cap.approved_usage_patterns.dependencies]
    assert "platform-http-client" in dep_patterns
    dep = next(p for p in cap.approved_usage_patterns.dependencies if p.pattern == "platform-http-client")
    assert dep.weight == SignalWeight.HIGH


def test_extract_catalog_import_patterns_include_module_and_exports(platform_manifest_file):
    raw = yaml.safe_load(platform_manifest_file.read_text())
    catalog = extract_catalog_from_platform_manifest(platform_manifest_file, raw)
    cap = catalog.capabilities[0]
    patterns = [p.pattern for p in cap.approved_usage_patterns.imports]
    assert "platform_http_client" in patterns
    assert "platform_http_client.PlatformHttpClient" in patterns
    assert "platform_http_client.HttpClientConfig" in patterns


def test_extract_catalog_import_export_patterns_are_high_weight(platform_manifest_file):
    raw = yaml.safe_load(platform_manifest_file.read_text())
    catalog = extract_catalog_from_platform_manifest(platform_manifest_file, raw)
    cap = catalog.capabilities[0]
    export_pattern = next(
        p for p in cap.approved_usage_patterns.imports
        if p.pattern == "platform_http_client.PlatformHttpClient"
    )
    assert export_pattern.weight == SignalWeight.HIGH


def test_extract_catalog_module_pattern_is_medium_weight(platform_manifest_file):
    raw = yaml.safe_load(platform_manifest_file.read_text())
    catalog = extract_catalog_from_platform_manifest(platform_manifest_file, raw)
    cap = catalog.capabilities[0]
    module_pattern = next(
        p for p in cap.approved_usage_patterns.imports
        if p.pattern == "platform_http_client"
    )
    assert module_pattern.weight == SignalWeight.MEDIUM


def test_extract_catalog_eligibility_rules(platform_manifest_file):
    raw = yaml.safe_load(platform_manifest_file.read_text())
    catalog = extract_catalog_from_platform_manifest(platform_manifest_file, raw)
    cap = catalog.capabilities[0]
    assert "platform-http-client" in cap.eligibility_rules.include_if_dependency
    assert "platform_http_client" in cap.eligibility_rules.include_if_import_prefix


def test_extract_catalog_source_is_platform_repo(platform_manifest_file):
    raw = yaml.safe_load(platform_manifest_file.read_text())
    catalog = extract_catalog_from_platform_manifest(platform_manifest_file, raw)
    assert catalog.capabilities[0].source == "platform_repo"


def test_extract_catalog_conventions(platform_manifest_file):
    raw = yaml.safe_load(platform_manifest_file.read_text())
    catalog = extract_catalog_from_platform_manifest(platform_manifest_file, raw)
    assert "platform_" in catalog.platform_conventions.approved_import_prefixes
    assert "platform-" in catalog.platform_conventions.approved_dependency_prefixes
    assert "platform." in catalog.platform_conventions.config_key_prefixes


def test_extract_catalog_exceptions_are_empty(platform_manifest_file):
    raw = yaml.safe_load(platform_manifest_file.read_text())
    catalog = extract_catalog_from_platform_manifest(platform_manifest_file, raw)
    assert catalog.exceptions == []


def test_extract_catalog_no_anti_patterns(platform_manifest_file):
    """Anti-patterns cannot be inferred from platform repo code."""
    raw = yaml.safe_load(platform_manifest_file.read_text())
    catalog = extract_catalog_from_platform_manifest(platform_manifest_file, raw)
    cap = catalog.capabilities[0]
    assert cap.anti_patterns.class_name_patterns == []
    assert cap.anti_patterns.dependency_patterns == []
    assert cap.anti_patterns.code_patterns == []


# ---------------------------------------------------------------------------
# load_catalog() auto-detection
# ---------------------------------------------------------------------------

def test_load_catalog_auto_detects_platform_manifest(platform_manifest_file):
    """load_catalog() routes to extractor when file contains platform_repos key."""
    catalog = load_catalog(platform_manifest_file)
    assert len(catalog.capabilities) == 1
    assert catalog.capabilities[0].capability_id == "platform_http_client"


def test_load_catalog_platform_manifest_produces_valid_catalog(platform_manifest_file):
    catalog = load_catalog(platform_manifest_file)
    assert catalog.catalog_version == "1.0"
    assert catalog.owner == "platform-team"


def test_load_catalog_still_loads_classic_yaml(tmp_path):
    """Existing catalog.yaml files continue to work unchanged."""
    classic = """\
catalog_version: "1.0"
owner: platform-team
platform_conventions:
  python:
    approved_import_prefixes: ["platform_"]
    approved_dependency_prefixes: ["platform-"]
capabilities:
  - capability_id: platform_http_client
    name: Platform HTTP Client
    status: stable
    approved_usage_patterns:
      dependencies:
        - pattern: "platform-http-client"
          weight: high
    eligibility_rules:
      include_if_dependency: ["platform-http-client"]
    minimum_evidence_required:
      adoption: 1
      reinvention: 1
exceptions: []
"""
    p = tmp_path / "catalog.yaml"
    p.write_text(classic)
    catalog = load_catalog(p)
    assert catalog.capabilities[0].capability_id == "platform_http_client"


def test_load_catalog_setup_py_fallback(tmp_path):
    """Extractor falls back to setup.py when pyproject.toml is absent."""
    zip_path = _make_platform_zip(
        tmp_path,
        {
            "setup.py": SETUP_PY,
            "src/platform_auth_client/__init__.py": '__all__ = ["AuthClient"]\n',
        },
        name="platform-auth-client",
    )
    manifest = {
        "platform_manifest_version": "1.0",
        "platform_repos": [
            {"repo_id": "platform-auth-client", "archive": str(zip_path), "status": "stable"}
        ],
    }
    path = tmp_path / "pm.yaml"
    path.write_text(yaml.dump(manifest))
    catalog = load_catalog(path)
    cap = catalog.capabilities[0]
    assert cap.capability_id == "platform_auth_client"
    dep_patterns = [p.pattern for p in cap.approved_usage_patterns.dependencies]
    assert "platform-auth-client" in dep_patterns


def test_load_catalog_multiple_platform_repos(tmp_path):
    zip1 = _make_platform_zip(tmp_path, {"pyproject.toml": PYPROJECT_TOML,
                                          "src/platform_http_client/__init__.py": INIT_WITH_ALL})
    zip2 = _make_platform_zip(
        tmp_path,
        {"setup.py": SETUP_PY, "src/platform_auth_client/__init__.py": '__all__ = ["AuthClient"]\n'},
        name="platform-auth-client",
    )
    manifest = {
        "platform_manifest_version": "1.0",
        "platform_repos": [
            {"repo_id": "platform-http-client", "archive": str(zip1), "status": "stable"},
            {"repo_id": "platform-auth-client", "archive": str(zip2), "status": "beta"},
        ],
    }
    path = tmp_path / "multi.yaml"
    path.write_text(yaml.dump(manifest))
    catalog = load_catalog(path)
    assert len(catalog.capabilities) == 2
    ids = {c.capability_id for c in catalog.capabilities}
    assert ids == {"platform_http_client", "platform_auth_client"}
