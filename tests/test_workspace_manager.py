"""Tests for workspace/manager.py"""
import zipfile
import tarfile
import io
import pytest
from pathlib import Path
from platform_capability.workspace.manager import WorkspaceManager


@pytest.fixture
def manager(tmp_path):
    return WorkspaceManager(base_dir=str(tmp_path / "workspaces"))


def _make_zip(tmp_path: Path, name: str, files: dict[str, str]) -> str:
    p = tmp_path / f"{name}.zip"
    with zipfile.ZipFile(p, "w") as zf:
        for rel, content in files.items():
            zf.writestr(rel, content)
    return str(p)


def _make_tarball(tmp_path: Path, name: str, files: dict[str, str]) -> str:
    p = tmp_path / f"{name}.tar.gz"
    with tarfile.open(p, "w:gz") as tf:
        for rel, content in files.items():
            encoded = content.encode()
            info = tarfile.TarInfo(name=rel)
            info.size = len(encoded)
            tf.addfile(info, io.BytesIO(encoded))
    return str(p)


def test_prepare_zip(tmp_path, manager):
    archive = _make_zip(tmp_path, "test-repo", {
        "requirements.txt": "requests==2.31.0\n",
        "src/app.py": "import requests\n",
    })
    ws = manager.prepare("test-repo", archive)
    assert ws.repo_id == "test-repo"
    assert "requirements.txt" in ws.dependency_files
    assert any("app.py" in f for f in ws.source_files)


def test_prepare_tarball(tmp_path, manager):
    archive = _make_tarball(tmp_path, "test-repo", {
        "requirements.txt": "flask==3.0.0\n",
        "app.py": "from flask import Flask\n",
    })
    ws = manager.prepare("test-repo", archive)
    assert "requirements.txt" in ws.dependency_files


def test_prepare_detects_python(tmp_path, manager):
    archive = _make_zip(tmp_path, "py-repo", {
        "app.py": "print('hello')\n",
        "util.py": "def helper(): pass\n",
    })
    ws = manager.prepare("py-repo", archive)
    assert "python" in ws.detected_languages


def test_prepare_ignores_pycache(tmp_path, manager):
    archive = _make_zip(tmp_path, "dirty-repo", {
        "app.py": "import requests\n",
        "__pycache__/app.cpython-311.pyc": "\x00\x00\x00",
        ".venv/lib/requests/__init__.py": "# requests",
    })
    ws = manager.prepare("dirty-repo", archive)
    rel_paths = [f.relative_path for f in ws.file_tree]
    assert not any("__pycache__" in p for p in rel_paths)
    assert not any(".venv" in p for p in rel_paths)


def test_prepare_ignores_pyc_extension(tmp_path, manager):
    archive = _make_zip(tmp_path, "dirty2", {
        "app.py": "pass\n",
        "app.pyc": "\x00binary",
    })
    ws = manager.prepare("dirty2", archive)
    exts = [f.extension for f in ws.file_tree]
    assert ".pyc" not in exts


def test_prepare_strips_single_top_dir(tmp_path, manager):
    """Archives that wrap everything in a top-level folder should be stripped."""
    archive = _make_zip(tmp_path, "wrapped", {
        "my-repo-main/requirements.txt": "requests==2.31.0\n",
        "my-repo-main/app.py": "import requests\n",
    })
    ws = manager.prepare("wrapped", archive)
    assert "requirements.txt" in ws.dependency_files


def test_prepare_config_files(tmp_path, manager):
    archive = _make_zip(tmp_path, "config-repo", {
        "app.py": "pass\n",
        "config/settings.yaml": "platform:\n  enabled: true\n",
        ".env": "DATABASE_URL=postgres://...\n",
    })
    ws = manager.prepare("config-repo", archive)
    cfg_rels = ws.config_files
    assert any(".yaml" in f or ".yml" in f for f in cfg_rels)


def test_prepare_unsupported_format(tmp_path, manager):
    bad = tmp_path / "repo.rar"
    bad.write_bytes(b"RAR archive content")
    with pytest.raises(ValueError, match="Unsupported archive format"):
        manager.prepare("bad-repo", str(bad))


def test_cleanup(tmp_path, manager):
    archive = _make_zip(tmp_path, "cleanup-repo", {"app.py": "pass\n"})
    manager.prepare("cleanup-repo", archive)
    ws_path = Path(manager._base_dir) / "cleanup-repo"
    assert ws_path.exists()
    manager.cleanup()
    assert not ws_path.exists()


def test_file_entries_have_stable_ids(tmp_path, manager):
    archive = _make_zip(tmp_path, "id-repo", {
        "a.py": "pass\n",
        "b.py": "pass\n",
    })
    ws = manager.prepare("id-repo", archive)
    ids = [f.file_id for f in ws.file_tree]
    assert len(ids) == len(set(ids))  # all unique
