"""Tests for catalog/loader.py"""
import pytest
from pathlib import Path
from platform_capability.catalog.loader import load_catalog
from platform_capability.models import CapabilityStatus, SignalWeight
from tests.conftest import MINIMAL_CATALOG_YAML


@pytest.fixture
def catalog_file(tmp_path) -> Path:
    p = tmp_path / "catalog.yaml"
    p.write_text(MINIMAL_CATALOG_YAML)
    return p


def test_load_catalog_basic(catalog_file):
    catalog = load_catalog(catalog_file)
    assert catalog.catalog_version == "1.0"
    assert len(catalog.capabilities) == 1


def test_load_catalog_capability_fields(catalog_file):
    catalog = load_catalog(catalog_file)
    cap = catalog.capabilities[0]
    assert cap.capability_id == "platform_http_client"
    assert cap.name == "Platform HTTP Client"
    assert cap.status == CapabilityStatus.STABLE


def test_load_catalog_approved_patterns(catalog_file):
    catalog = load_catalog(catalog_file)
    cap = catalog.capabilities[0]
    assert len(cap.approved_usage_patterns.dependencies) == 1
    dep = cap.approved_usage_patterns.dependencies[0]
    assert dep.pattern == "platform-http-client"
    assert dep.weight == SignalWeight.HIGH


def test_load_catalog_anti_patterns(catalog_file):
    catalog = load_catalog(catalog_file)
    cap = catalog.capabilities[0]
    assert len(cap.anti_patterns.class_name_patterns) == 1
    assert cap.anti_patterns.class_name_patterns[0].pattern == "RetrySession"
    assert len(cap.anti_patterns.dependency_patterns) == 1
    assert len(cap.anti_patterns.code_patterns) == 1


def test_load_catalog_eligibility_rules(catalog_file):
    catalog = load_catalog(catalog_file)
    cap = catalog.capabilities[0]
    assert "requests" in cap.eligibility_rules.include_if_dependency
    assert "platform-http-client" in cap.eligibility_rules.include_if_dependency


def test_load_catalog_platform_conventions(catalog_file):
    catalog = load_catalog(catalog_file)
    assert "platform_" in catalog.platform_conventions.approved_import_prefixes
    assert "platform-" in catalog.platform_conventions.approved_dependency_prefixes


def test_load_catalog_exceptions(tmp_path):
    yaml_with_exceptions = MINIMAL_CATALOG_YAML + """
exceptions:
  - repo_id: legacy-repo
    capability_id: platform_http_client
    reason: Pre-platform legacy service
    approved_by: platform-team
    approved_at: "2026-01-01"
    expires: "2026-12-31"
"""
    p = tmp_path / "catalog_exc.yaml"
    p.write_text(yaml_with_exceptions)
    catalog = load_catalog(p)
    assert len(catalog.exceptions) == 1
    assert catalog.exceptions[0].repo_id == "legacy-repo"


def test_load_catalog_file_not_found():
    with pytest.raises(FileNotFoundError, match="Catalog not found"):
        load_catalog("/nonexistent/path/catalog.yaml")


def test_load_catalog_string_patterns(tmp_path):
    """Test catalog where patterns are plain strings (no weight field)."""
    yaml = """
catalog_version: "1.0"
capabilities:
  - capability_id: test_cap
    name: Test Capability
    status: stable
    approved_usage_patterns:
      dependencies:
        - "test-lib"
    anti_patterns:
      class_name_patterns:
        - "CustomImpl"
    eligibility_rules:
      include_if_dependency:
        - "test-lib"
    minimum_evidence_required:
      adoption: 1
      reinvention: 1
exceptions: []
"""
    p = tmp_path / "catalog_str.yaml"
    p.write_text(yaml)
    catalog = load_catalog(p)
    cap = catalog.capabilities[0]
    assert cap.approved_usage_patterns.dependencies[0].pattern == "test-lib"
    assert cap.approved_usage_patterns.dependencies[0].weight == SignalWeight.MEDIUM
    assert cap.anti_patterns.class_name_patterns[0].pattern == "CustomImpl"


def test_load_catalog_empty_capabilities(tmp_path):
    yaml = "catalog_version: '1.0'\ncapabilities: []\nexceptions: []\n"
    p = tmp_path / "empty.yaml"
    p.write_text(yaml)
    catalog = load_catalog(p)
    assert catalog.capabilities == []
