from __future__ import annotations

import hashlib
import shutil
import tarfile
import tempfile
import zipfile
from pathlib import Path

from platform_capability.config import settings
from platform_capability.models import FileEntry, WorkspaceManifest

LANGUAGE_MAP = {
    ".py": "python",
    ".java": "java",
    ".kt": "kotlin",
    ".scala": "scala",
    ".js": "javascript",
    ".ts": "typescript",
    ".go": "go",
    ".rb": "ruby",
}

DEP_FILES = {
    "requirements.txt", "setup.py", "setup.cfg", "pyproject.toml",
    "pom.xml", "build.gradle", "build.gradle.kts", "package.json",
    "Pipfile", "Pipfile.lock", "poetry.lock",
}

CONFIG_EXTENSIONS = {".yaml", ".yml", ".env", ".ini", ".cfg", ".json", ".properties", ".toml"}


class WorkspaceManager:
    def __init__(self, base_dir: str | None = None):
        self._base_dir = base_dir or tempfile.mkdtemp(prefix="pci-workspace-")
        self._workspaces: list[str] = []

    def prepare(self, repo_id: str, archive_path: str) -> WorkspaceManifest:
        archive = Path(archive_path)
        workspace_path = Path(self._base_dir) / repo_id
        workspace_path.mkdir(parents=True, exist_ok=True)
        self._workspaces.append(str(workspace_path))

        self._extract(archive, workspace_path)

        # Strip common single top-level directory wrapping (e.g. repo-main/)
        entries = list(workspace_path.iterdir())
        if len(entries) == 1 and entries[0].is_dir():
            inner = entries[0]
            for item in inner.iterdir():
                shutil.move(str(item), str(workspace_path / item.name))
            inner.rmdir()

        return self._build_manifest(repo_id, workspace_path)

    def _extract(self, archive: Path, dest: Path) -> None:
        suffix = "".join(archive.suffixes).lower()
        if suffix in (".zip",):
            with zipfile.ZipFile(archive) as zf:
                zf.extractall(dest)
        elif suffix in (".tar.gz", ".tgz", ".tar.bz2", ".tar"):
            with tarfile.open(archive) as tf:
                tf.extractall(dest)
        else:
            raise ValueError(f"Unsupported archive format: {archive.name}")

    def _build_manifest(self, repo_id: str, workspace_path: Path) -> WorkspaceManifest:
        file_entries: list[FileEntry] = []
        languages: set[str] = set()
        dep_files: list[str] = []
        config_files: list[str] = []
        source_files: list[str] = []

        for abs_path in workspace_path.rglob("*"):
            if not abs_path.is_file():
                continue

            rel = abs_path.relative_to(workspace_path)
            parts = rel.parts

            # Skip ignored directories
            if any(p in settings.ignored_dirs for p in parts):
                continue

            ext = abs_path.suffix.lower()
            if ext in settings.ignored_extensions:
                continue

            file_id = hashlib.md5(str(rel).encode()).hexdigest()[:12]
            lang = LANGUAGE_MAP.get(ext, "")
            if lang:
                languages.add(lang)

            rel_str = str(rel)
            entry = FileEntry(
                file_id=file_id,
                relative_path=rel_str,
                absolute_path=str(abs_path),
                extension=ext,
                size_bytes=abs_path.stat().st_size,
                language=lang,
            )
            file_entries.append(entry)

            name = abs_path.name
            if name in DEP_FILES:
                dep_files.append(rel_str)
            elif ext in CONFIG_EXTENSIONS:
                config_files.append(rel_str)
            elif lang:
                source_files.append(rel_str)

        workspace_id = hashlib.md5(f"{repo_id}-{workspace_path}".encode()).hexdigest()[:12]
        return WorkspaceManifest(
            workspace_id=workspace_id,
            repo_id=repo_id,
            workspace_path=str(workspace_path),
            detected_languages=sorted(languages),
            file_tree=file_entries,
            dependency_files=dep_files,
            config_files=config_files,
            source_files=source_files,
        )

    def cleanup(self) -> None:
        for ws in self._workspaces:
            shutil.rmtree(ws, ignore_errors=True)
        self._workspaces.clear()
