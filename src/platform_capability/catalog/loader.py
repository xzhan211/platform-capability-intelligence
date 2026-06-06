from __future__ import annotations

import yaml
from pathlib import Path

from platform_capability.models import (
    CapabilityCatalog,
    Capability,
    PlatformConventions,
    CapabilityException,
    ApprovedUsagePatterns,
    AntiPatterns,
    EligibilityRules,
    EvidenceRules,
    MinimumEvidence,
    PatternRule,
    SignalWeight,
    CapabilityStatus,
)


def _parse_pattern_list(raw: list) -> list[PatternRule]:
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


def load_catalog(catalog_path: str | Path) -> CapabilityCatalog:
    path = Path(catalog_path)
    if not path.exists():
        raise FileNotFoundError(f"Catalog not found: {path}")

    with open(path) as f:
        raw = yaml.safe_load(f)

    conventions_raw = raw.get("platform_conventions", {})
    py_conv = conventions_raw.get("python", {})
    conventions = PlatformConventions(
        approved_import_prefixes=py_conv.get("approved_import_prefixes", []),
        approved_dependency_prefixes=py_conv.get("approved_dependency_prefixes", []),
        config_key_prefixes=conventions_raw.get("config_key_prefixes", []),
    )

    capabilities = []
    for cap_raw in raw.get("capabilities", []):
        aup_raw = cap_raw.get("approved_usage_patterns", {})
        ap_raw = cap_raw.get("anti_patterns", {})
        er_raw = cap_raw.get("eligibility_rules", {})
        ev_raw = cap_raw.get("evidence_rules", {})
        me_raw = cap_raw.get("minimum_evidence_required", {})

        cap = Capability(
            capability_id=cap_raw["capability_id"],
            name=cap_raw.get("name", cap_raw["capability_id"]),
            category=cap_raw.get("category", ""),
            owner_team=cap_raw.get("owner_team", ""),
            status=CapabilityStatus(cap_raw.get("status", "stable")),
            maturity=cap_raw.get("maturity", "stable"),
            catalog_version=str(raw.get("catalog_version", "1.0")),
            source=cap_raw.get("source", "manual"),
            description=cap_raw.get("description", ""),
            documentation_url=cap_raw.get("documentation_url", ""),
            recommended_for=cap_raw.get("recommended_for", []),
            approved_usage_patterns=ApprovedUsagePatterns(
                dependencies=_parse_pattern_list(aup_raw.get("dependencies", [])),
                imports=_parse_pattern_list(aup_raw.get("imports", [])),
                config_keys=_parse_pattern_list(aup_raw.get("config_keys", [])),
                templates=_parse_pattern_list(aup_raw.get("templates", [])),
            ),
            anti_patterns=AntiPatterns(
                class_name_patterns=_parse_pattern_list(ap_raw.get("class_name_patterns", [])),
                dependency_patterns=_parse_pattern_list(ap_raw.get("dependency_patterns", [])),
                code_patterns=_parse_pattern_list(ap_raw.get("code_patterns", [])),
            ),
            eligibility_rules=EligibilityRules(
                include_if_dependency=er_raw.get("include_if_dependency", []),
                include_if_import_prefix=er_raw.get("include_if_import_prefix", []),
                include_if_config_key_prefix=er_raw.get("include_if_config_key_prefix", []),
                include_if_file_pattern=er_raw.get("include_if_file_pattern", []),
            ),
            evidence_rules=EvidenceRules(
                collect_files=ev_raw.get("collect_files", []),
                max_snippet_lines=ev_raw.get("max_snippet_lines", 40),
            ),
            minimum_evidence_required=MinimumEvidence(
                adoption=me_raw.get("adoption", 1),
                reinvention=me_raw.get("reinvention", 1),
            ),
        )
        capabilities.append(cap)

    exceptions = []
    for ex_raw in raw.get("exceptions", []):
        exceptions.append(CapabilityException(
            repo_id=ex_raw["repo_id"],
            capability_id=ex_raw.get("capability_id", ""),
            reason=ex_raw.get("reason", ""),
            approved_by=ex_raw.get("approved_by", ""),
            approved_at=ex_raw.get("approved_at", ""),
            expires=ex_raw.get("expires"),
        ))

    return CapabilityCatalog(
        catalog_version=str(raw.get("catalog_version", "1.0")),
        generated_at=raw.get("generated_at", ""),
        owner=raw.get("owner", ""),
        platform_conventions=conventions,
        capabilities=capabilities,
        exceptions=exceptions,
    )
