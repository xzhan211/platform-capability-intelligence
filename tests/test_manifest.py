"""Tests for workspace/manifest.py"""
import pytest
from pathlib import Path
from platform_capability.workspace.manifest import load_manifest
from tests.conftest import MINIMAL_MANIFEST_YAML


@pytest.fixture
def make_manifest(tmp_path, make_zip):
    def _make(extra_yaml: str = "") -> tuple[str, str]:
        archive = make_zip("test-repo", {"requirements.txt": "requests==2.31.0\n"})
        yaml = MINIMAL_MANIFEST_YAML.format(archive_path=archive) + extra_yaml
        manifest_path = tmp_path / "scan_manifest.yaml"
        manifest_path.write_text(yaml)
        return str(manifest_path), archive
    return _make


def test_load_manifest_basic(make_manifest):
    manifest_path, archive = make_manifest()
    manifest = load_manifest(manifest_path)
    assert manifest.scan_batch_id == "test-batch-001"
    assert len(manifest.repos) == 1


def test_load_manifest_repo_fields(make_manifest):
    manifest_path, _ = make_manifest()
    manifest = load_manifest(manifest_path)
    repo = manifest.repos[0]
    assert repo.repo_id == "test-repo"
    assert repo.tenant_id == "test-team"
    assert repo.branch == "main"


def test_load_manifest_archive_resolved(make_manifest):
    manifest_path, archive = make_manifest()
    manifest = load_manifest(manifest_path)
    assert Path(manifest.repos[0].archive).exists()


def test_load_manifest_relative_archive(tmp_path):
    """Archive path relative to manifest directory is resolved correctly."""
    import zipfile
    # Create a subdirectory for the manifest, with the archive next to it
    manifest_dir = tmp_path / "scans"
    manifest_dir.mkdir()
    archive_path = manifest_dir / "my-repo.zip"
    with zipfile.ZipFile(archive_path, "w") as zf:
        zf.writestr("requirements.txt", "requests==2.31.0\n")

    yaml = """
scan_batch_id: rel-batch
repos:
  - repo_id: my-repo
    repo_name: my-repo
    tenant_id: my-team
    archive: ./my-repo.zip
"""
    manifest_path = manifest_dir / "manifest.yaml"
    manifest_path.write_text(yaml)
    manifest = load_manifest(manifest_path)
    assert Path(manifest.repos[0].archive).exists()


def test_load_manifest_file_not_found():
    with pytest.raises(FileNotFoundError, match="Manifest not found"):
        load_manifest("/nonexistent/manifest.yaml")


def test_load_manifest_archive_missing(tmp_path):
    yaml = """
scan_batch_id: bad-batch
repos:
  - repo_id: ghost-repo
    repo_name: ghost-repo
    tenant_id: ghost-team
    archive: /nonexistent/ghost.zip
"""
    p = tmp_path / "bad_manifest.yaml"
    p.write_text(yaml)
    with pytest.raises(FileNotFoundError, match="Archive not found"):
        load_manifest(p)


def test_load_manifest_default_branch(make_manifest):
    manifest_path, _ = make_manifest()
    manifest = load_manifest(manifest_path)
    assert manifest.repos[0].branch == "main"


def test_load_manifest_multiple_repos(tmp_path, make_zip):
    a1 = make_zip("repo1", {"requirements.txt": "requests==2.31.0\n"})
    a2 = make_zip("repo2", {"requirements.txt": "flask==3.0.0\n"})
    yaml = f"""
scan_batch_id: multi-batch
repos:
  - repo_id: repo1
    repo_name: repo1
    tenant_id: team1
    archive: {a1}
  - repo_id: repo2
    repo_name: repo2
    tenant_id: team2
    archive: {a2}
"""
    p = tmp_path / "multi.yaml"
    p.write_text(yaml)
    manifest = load_manifest(p)
    assert len(manifest.repos) == 2
    assert manifest.repos[0].repo_id == "repo1"
    assert manifest.repos[1].tenant_id == "team2"
