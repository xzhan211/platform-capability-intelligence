from __future__ import annotations

import yaml
from pathlib import Path
from datetime import datetime, timezone

from platform_capability.models import ScanManifest, RepoDefinition


def load_manifest(manifest_path: str | Path) -> ScanManifest:
    path = Path(manifest_path)
    if not path.exists():
        raise FileNotFoundError(f"Manifest not found: {path}")

    with open(path) as f:
        raw = yaml.safe_load(f)

    manifest_dir = path.parent
    repos = []
    for r in raw.get("repos", []):
        archive = r["archive"]
        # Resolve relative paths against the manifest directory
        if not Path(archive).is_absolute():
            archive = str(manifest_dir / archive)
        if not Path(archive).exists():
            raise FileNotFoundError(f"Archive not found: {archive} (repo: {r['repo_id']})")
        repos.append(RepoDefinition(
            repo_id=r["repo_id"],
            repo_name=r.get("repo_name", r["repo_id"]),
            tenant_id=r.get("tenant_id", "unknown"),
            archive=archive,
            branch=r.get("branch", "main"),
            commit_sha=r.get("commit_sha"),
        ))

    return ScanManifest(
        scan_batch_id=raw.get("scan_batch_id", f"batch-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"),
        scan_timestamp=raw.get("scan_timestamp", datetime.now(timezone.utc).isoformat()),
        catalog_version=raw.get("catalog_version", ""),
        repos=repos,
    )
