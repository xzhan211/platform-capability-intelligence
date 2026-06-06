from __future__ import annotations

import ast
import re
import shutil
import tarfile
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import yaml

from platform_capability.models import (
    ApprovedUsagePatterns,
    AntiPatterns,
    Capability,
    CapabilityCatalog,
    CapabilityStatus,
    EligibilityRules,
    EvidenceRules,
    MinimumEvidence,
    PatternRule,
    PlatformConventions,
    SignalWeight,
)

try:
    import tomllib  # Python 3.11+
except ImportError:
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ImportError:
        tomllib = None  # type: ignore[assignment]


def extract_catalog_from_platform_manifest(
    manifest_path: Path, raw: dict
) -> CapabilityCatalog:
    manifest_dir = manifest_path.parent
    conventions = _parse_conventions(raw.get("platform_conventions", {}))

    capabilities: list[Capability] = []
    for repo_def in raw.get("platform_repos", []):
        archive = manifest_dir / repo_def["archive"]
        meta = {k: v for k, v in repo_def.items() if k not in ("repo_id", "archive")}
        cap = _extract_capability_from_archive(archive, meta)
        capabilities.append(cap)

    return CapabilityCatalog(
        catalog_version=raw.get("platform_manifest_version", "1.0"),
        generated_at=datetime.now(timezone.utc).isoformat(),
        owner=raw.get("owner", ""),
        platform_conventions=conventions,
        capabilities=capabilities,
        exceptions=[],
    )


def _extract_capability_from_archive(archive: Path, meta: dict) -> Capability:
    tmp = tempfile.mkdtemp(prefix="pci-platform-")
    try:
        _unpack(archive, Path(tmp))
        root = _unwrap_root(Path(tmp))
        return _build_capability(root, meta)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _unpack(archive: Path, dest: Path) -> None:
    suffix = "".join(archive.suffixes).lower()
    if suffix == ".zip":
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(dest)
    elif suffix in (".tar.gz", ".tgz", ".tar.bz2", ".tar"):
        with tarfile.open(archive) as tf:
            tf.extractall(dest)
    else:
        raise ValueError(f"Unsupported archive format: {archive.name}")


def _unwrap_root(path: Path) -> Path:
    entries = list(path.iterdir())
    if len(entries) == 1 and entries[0].is_dir():
        return entries[0]
    return path


def _build_capability(root: Path, meta: dict) -> Capability:
    pyproject = _parse_pyproject(root)
    package_name = pyproject["name"]          # e.g. "platform-http-client"
    module_name = package_name.replace("-", "_")  # e.g. "platform_http_client"
    description = pyproject.get("description", "")
    version = pyproject.get("version", "")

    exports = _parse_exports(root, module_name)

    # approved_usage_patterns: dependency match + import matches per export
    dep_patterns = [PatternRule(pattern=package_name, weight=SignalWeight.HIGH)]
    import_patterns = [PatternRule(pattern=module_name, weight=SignalWeight.MEDIUM)]
    for export in exports:
        import_patterns.append(
            PatternRule(pattern=f"{module_name}.{export}", weight=SignalWeight.HIGH)
        )

    status_str = meta.get("status", "stable")
    try:
        status = CapabilityStatus(status_str)
    except ValueError:
        status = CapabilityStatus.STABLE

    catalog_meta = pyproject.get("tool_platform", {})

    # eligibility: use [tool.platform.eligibility_rules] if declared, else narrow default
    elig_raw = catalog_meta.get("eligibility_rules", {})
    eligibility = EligibilityRules(
        include_if_dependency=elig_raw.get("include_if_dependency", [package_name]),
        include_if_import_prefix=elig_raw.get("include_if_import_prefix", [module_name]),
    )

    # anti_patterns: use [tool.platform.anti_patterns] if declared
    ap_raw = catalog_meta.get("anti_patterns", {})
    anti_patterns = AntiPatterns(
        class_name_patterns=_parse_pattern_rules(ap_raw.get("class_name_patterns", [])),
        dependency_patterns=_parse_pattern_rules(ap_raw.get("dependency_patterns", [])),
        code_patterns=_parse_pattern_rules(ap_raw.get("code_patterns", [])),
    )

    return Capability(
        capability_id=module_name,
        name=catalog_meta.get("name", _humanize(package_name)),
        category=meta.get("category", catalog_meta.get("category", "")),
        owner_team=meta.get("owner_team", catalog_meta.get("owner_team", "")),
        status=status,
        maturity=status_str,
        catalog_version=version,
        source="platform_repo",
        description=description,
        documentation_url=catalog_meta.get("documentation_url", ""),
        recommended_for=catalog_meta.get("recommended_for", []),
        approved_usage_patterns=ApprovedUsagePatterns(
            dependencies=dep_patterns,
            imports=import_patterns,
        ),
        anti_patterns=anti_patterns,
        eligibility_rules=eligibility,
        evidence_rules=EvidenceRules(
            collect_files=["requirements.txt", "setup.py", "pyproject.toml", "*.py"],
            max_snippet_lines=30,
        ),
        minimum_evidence_required=MinimumEvidence(adoption=1, reinvention=1),
    )


def _parse_pyproject(root: Path) -> dict:
    pyproject_path = root / "pyproject.toml"
    if pyproject_path.exists() and tomllib is not None:
        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)
        project = data.get("project", {})
        tool_platform = data.get("tool", {}).get("platform", {})
        return {
            "name": project.get("name", root.name),
            "version": project.get("version", ""),
            "description": project.get("description", ""),
            "tool_platform": tool_platform,
        }

    # Fallback: parse setup.py name= line with regex
    setup_py = root / "setup.py"
    if setup_py.exists():
        text = setup_py.read_text()
        m = re.search(r'name\s*=\s*["\']([^"\']+)["\']', text)
        name = m.group(1) if m else root.name
        m2 = re.search(r'version\s*=\s*["\']([^"\']+)["\']', text)
        version = m2.group(1) if m2 else ""
        return {"name": name, "version": version, "description": "", "tool_platform": {}}

    return {"name": root.name, "version": "", "description": "", "tool_platform": {}}


def _parse_exports(root: Path, module_name: str) -> list[str]:
    # Look for __init__.py under src/<module>/ or <module>/
    candidates = [
        root / "src" / module_name / "__init__.py",
        root / module_name / "__init__.py",
    ]
    init_path = next((p for p in candidates if p.exists()), None)
    if not init_path:
        return []

    source = init_path.read_text(errors="ignore")

    # Try __all__ first
    try:
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Assign)
                and any(
                    isinstance(t, ast.Name) and t.id == "__all__"
                    for t in node.targets
                )
                and isinstance(node.value, ast.List)
            ):
                return [
                    elt.s if isinstance(elt, ast.Constant) else ""
                    for elt in node.value.elts
                    if isinstance(elt, ast.Constant)
                ]
    except SyntaxError:
        pass

    # Fallback: top-level class and function names that don't start with _
    names = []
    for m in re.finditer(r"^(?:class|def)\s+([A-Za-z][A-Za-z0-9_]*)", source, re.MULTILINE):
        name = m.group(1)
        if not name.startswith("_"):
            names.append(name)
    return names


def _parse_pattern_rules(raw: list) -> list[PatternRule]:
    result = []
    for item in raw:
        if isinstance(item, str):
            result.append(PatternRule(pattern=item))
        elif isinstance(item, dict):
            result.append(PatternRule(
                pattern=item.get("pattern", ""),
                weight=SignalWeight(item.get("weight", "medium")),
                note=item.get("note", ""),
            ))
    return result


def _parse_conventions(raw: dict) -> PlatformConventions:
    py = raw.get("python", {})
    return PlatformConventions(
        approved_import_prefixes=py.get("approved_import_prefixes", []),
        approved_dependency_prefixes=py.get("approved_dependency_prefixes", []),
        config_key_prefixes=raw.get("config_key_prefixes", []),
    )


def _humanize(package_name: str) -> str:
    return " ".join(w.capitalize() for w in package_name.replace("-", " ").split())
