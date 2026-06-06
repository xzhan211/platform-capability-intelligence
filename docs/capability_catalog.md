# Capability Catalog

## 1. Purpose

The Capability Catalog is the source of truth for what the platform provides. The detection pipeline cannot determine whether a repository is reusing or reinventing a platform capability unless the platform capabilities are explicitly defined.

The catalog describes:

- capability identity;
- owner team;
- expected usage patterns;
- approved libraries, templates, APIs, and configurations;
- anti-patterns that suggest reinvention;
- eligibility rules;
- evidence collection rules;
- maturity and documentation status.

### How the App Learns What the Platform Provides

The app only knows what is registered in the catalog. Two catalog sources are supported, selected automatically based on file content.

#### Source A: Static YAML (`catalog.yaml`)

The platform team writes detection rules by hand. This is the only source that supports anti-patterns.

```
--catalog demo/catalog/catalog.yaml
```

Required fields per capability: `approved_usage_patterns`, `anti_patterns`, `eligibility_rules`. See the schema in section 3.

#### Source B: Platform Repo Extraction (`platform_manifest.yaml`)

Point `--catalog` at a `platform_manifest.yaml` instead of a `catalog.yaml`. The tool opens each platform library's archive and derives the catalog automatically.

```
--catalog demo/manifest/platform_manifest.yaml
```

`load_catalog()` auto-detects the format: if the file contains a `platform_repos:` key, it routes to the extractor; otherwise it parses as a classic catalog YAML.

**What is extracted automatically:**

| Source in platform repo | Derived catalog field |
|---|---|
| `pyproject.toml [project].name` | `capability_id` (underscored), dependency pattern (HIGH weight) |
| `pyproject.toml [project].description` | `description` |
| `__init__.py __all__` | per-export import patterns (HIGH weight) |
| module name | module import pattern (MEDIUM weight), `eligibility_rules` |
| `[tool.platform]` in pyproject.toml | `owner_team`, `documentation_url`, `recommended_for` |
| per-repo keys in platform manifest | `category`, `status`, `owner_team` |

**What cannot be extracted:**

Anti-patterns (reinvention signals) are always left empty when extracting from platform repos. There is no way to infer what a custom reimplementation looks like by reading the platform library itself — that knowledge must come from a human. Use static YAML if reinvention detection is needed.

**Platform manifest format:**

```yaml
platform_manifest_version: "1.0"
owner: platform-team

platform_conventions:
  python:
    approved_import_prefixes: ["platform_"]
    approved_dependency_prefixes: ["platform-"]
  config_key_prefixes: ["platform."]

platform_repos:
  - repo_id: platform-http-client
    archive: ../repos/platform-http-client.zip
    owner_team: platform-core
    category: integration
    status: stable
```

**Required platform repo layout:**

```
platform-http-client/
├── pyproject.toml               ← [project].name, description, version
│                                   [tool.platform] for catalog metadata
└── src/
    └── platform_http_client/
        └── __init__.py          ← __all__ = ["PlatformHttpClient", ...]
```

If `pyproject.toml` is absent the extractor falls back to `setup.py` (regex parsing of `name=` and `version=`). If no packaging file is found the repo directory name is used as the package name.

If `__init__.py` has no `__all__`, the extractor falls back to all top-level `class` and `def` names that do not start with `_`.

## 2. Two-Tier Detection Model

Not every platform capability has to be manually cataloged before the system provides value. Detection works in two tiers:

### Tier 1: Platform Namespace Detection (Generic, Optional)

If some platform capabilities follow a consistent naming convention (e.g., packages prefixed with `platform-` or imports from `company_platform.*`), a single generic block at the top of the catalog covers all of them at once.

```yaml
platform_conventions:
  python:
    approved_import_prefixes:
      - "company_platform."
      - "platform_"
    approved_dependency_prefixes:
      - "platform-"
  config_key_prefixes:
    - "platform."
```

This runs without any per-capability entry and answers: "Does this repo use the platform at all?" A repo matching any prefix gets a generic `USES_PLATFORM` signal. This is useful for broad adoption visibility even before the full catalog is built.

Capabilities that do not follow the naming convention are not covered by Tier 1 and require a specific catalog entry.

### Tier 2: Capability-Specific Detection (Per Capability, Incremental)

Per-capability entries are required for:
- capabilities that do not follow the platform naming convention;
- reinvention signal detection (always capability-specific — requires human knowledge of what a custom implementation looks like);
- eligibility rules;
- precise adoption confirmation beyond namespace matching.

The catalog is built incrementally. Start with the highest-value capability. The system improves as entries are added.

**Key principle:** Anti-patterns (reinvention signals) always require manual curation. There is no way to auto-derive what a custom reimplementation looks like. A human must define: "if we see `SnowflakeTokenManager` without our wrapper, that is reinvention."

## 3. Core Concepts

### Capability

A reusable platform-provided building block that tenants can adopt instead of implementing the same functionality themselves.

Examples:

- Snowflake authentication
- platform authentication wrapper
- logging and observability integration
- CI/CD template
- data access wrapper
- permissioning framework
- deployment template
- Kafka integration
- standard retry/error handling client
- secrets management pattern

### Tenant

A team, product group, service group, or application owner that uses or may use the platform.

### Repository

A source repository owned by a tenant. It is the primary unit of technical detection.

### Adoption

A repository or tenant is considered to have adopted a capability when it uses the approved platform-provided pattern, library, template, API, or configuration for that capability.

### Reinvention

A repository or tenant shows a reinvention signal when it appears to implement custom logic for a capability that the platform already provides.

### Eligibility

Not every tenant needs every capability. A repository should only be counted against a capability's adoption rate if it is eligible for that capability.

Example: A service that makes no HTTP calls should not lower the adoption rate of the Platform HTTP Client capability.

## 3. Capability Catalog Schema

The demo catalog (`demo/catalog/catalog.yaml`) uses the **Platform HTTP Client** capability as the reference implementation. The schema below reflects what is actually parsed by `catalog/loader.py`.

```yaml
catalog_version: "1.0"
generated_at: "2026-06-06"
owner: platform-team

# Tier 1: generic platform namespace detection (no per-capability work needed)
platform_conventions:
  python:
    approved_import_prefixes:
      - "platform_http_client"
      - "platform_"
    approved_dependency_prefixes:
      - "platform-"
  config_key_prefixes:
    - "platform."

capabilities:
  - capability_id: platform_http_client
    name: Platform HTTP Client
    category: integration
    owner_team: platform-core
    status: stable
    maturity: stable
    catalog_version: "1.0"
    source: manual           # manual | auto_generated | imported
    description: >
      Standard HTTP client with built-in retry, circuit breaker, and
      observability. Replaces direct use of requests or httpx.
    documentation_url: https://internal/docs/platform-http-client
    recommended_for:
      - services that call internal or external HTTP APIs

    approved_usage_patterns:
      dependencies:
        - pattern: "platform-http-client"
          weight: high        # one high-weight signal → ADOPTED
      imports:
        - pattern: "platform_http_client.PlatformHttpClient"
          weight: high
        - pattern: "platform_http_client"
          weight: medium      # corroborating signal

    anti_patterns:
      class_name_patterns:
        - pattern: "RetrySession"
          weight: high        # one high-weight signal → CUSTOM_IMPLEMENTATION
          note: "Custom retry session wrapping requests.Session"
        - pattern: "CustomRetry"
          weight: medium
          note: "Custom retry logic class"
      dependency_patterns:
        - pattern: "requests"
          weight: medium
          note: "Raw requests library without platform wrapper"
        - pattern: "httpx"
          weight: medium
          note: "Raw httpx library without platform wrapper"
      code_patterns:
        - pattern: "HTTPAdapter"
          weight: high
          note: "Custom HTTPAdapter — manual retry configuration"
        - pattern: "Retry("
          weight: high
          note: "urllib3 Retry object — manual retry configuration"

    eligibility_rules:
      include_if_dependency:
        - "requests"
        - "httpx"
        - "aiohttp"
        - "platform-http-client"
      include_if_import_prefix:
        - "requests"
        - "httpx"
        - "platform_http_client"

    evidence_rules:
      collect_files:
        - "requirements.txt"
        - "setup.py"
        - "pyproject.toml"
        - "*.py"
      max_snippet_lines: 30

    minimum_evidence_required:
      adoption: 1
      reinvention: 1

exceptions: []
```

### Eligibility Rule Field Names

The `eligibility_rules` block uses these field names (as parsed by `catalog/loader.py`):

```yaml
eligibility_rules:
  include_if_dependency:       # package name found in dependency files
  include_if_import_prefix:    # import statement starts with this prefix
  include_if_config_key_prefix: # config key starts with this prefix
  include_if_file_pattern:     # file name matches this glob pattern
```

### Signal Weight Classification Rules

The signal weight fields drive deterministic classification.

```text
ADOPTED:
  - At least 1 high-weight approved_usage_pattern signal, OR
  - 2+ medium-weight approved_usage_pattern signals

CUSTOM_IMPLEMENTATION:
  - At least 1 high-weight anti_pattern signal, OR
  - 2+ medium-weight anti_pattern signals
  - AND no high-weight adoption signal present

MISSING:
  - Repo is eligible
  - No adoption signal of any weight
  - No reinvention signal meeting CUSTOM_IMPLEMENTATION threshold

UNKNOWN:
  - Evidence is insufficient for any determination
  - Typically: eligible but only 1 medium-weight signal of any type

NOT_ELIGIBLE:
  - No eligibility rule matched

EXEMPT:
  - Repo appears in the exceptions list for this capability
  - Shown separately in dashboard; excluded from adoption rate denominator
```

## 4. Capability Statuses

Recommended lifecycle states:

- `draft`: entry created (manually or auto-generated) but not yet reviewed or activated; excluded from all scoring.
- `beta`: available to early adopters; included in adoption scoring.
- `stable`: recommended for broad adoption; included in adoption scoring.
- `deprecated`: should not be adopted by new tenants; still included in scoring to track remaining usage.
- `retired`: no longer supported; excluded from adoption scoring.

Only `beta` and `stable` capabilities are included in adoption rate calculations.

### Extracted Entry Example

When `source: platform_repo` is set, the extractor produces entries equivalent to:

```yaml
capability_id: platform_http_client
name: Platform Http Client
source: platform_repo      # set automatically by the extractor
status: stable
description: "Standard platform HTTP client with retry and observability."
approved_usage_patterns:
  dependencies:
    - pattern: "platform-http-client"
      weight: high         # from pyproject.toml [project].name
  imports:
    - pattern: "platform_http_client"
      weight: medium       # module-level pattern
    - pattern: "platform_http_client.PlatformHttpClient"
      weight: high         # from __init__.py __all__
    - pattern: "platform_http_client.HttpClientConfig"
      weight: high
anti_patterns: []          # always empty — requires human completion
eligibility_rules:
  include_if_dependency:
    - "platform-http-client"
  include_if_import_prefix:
    - "platform_http_client"
```

To add reinvention detection, supplement with a static `catalog.yaml` entry that adds `anti_patterns` and merge the two before running the scan, or extend the platform manifest with a future `anti_patterns_overlay` field.

## 5. Detection Signal Types

### Positive Adoption Signals

Evidence that the repository is using the approved platform capability:

- approved dependency exists;
- approved import exists;
- approved config key exists;
- approved CI/CD template is referenced;
- platform-provided API/client is used;
- README or onboarding docs reference the platform capability.

### Reinvention Signals

Evidence that the repository may have custom-built a capability:

- custom class names similar to platform capability implementation;
- direct use of lower-level third-party library without platform wrapper;
- duplicated authentication, permissioning, retry, logging, or data access logic;
- configuration keys that bypass platform conventions;
- similar code patterns across multiple tenants.

### Absence Signals

Evidence that a capability is expected but not detected:

- repository appears eligible;
- no approved dependency/import/template exists;
- no custom implementation is detected;
- capability status becomes `missing` or `unknown` depending on evidence strength.

## 6. Capability Detection Status

Each repository-capability pair should be classified as one of:

- `ADOPTED`: approved platform capability usage detected.
- `CUSTOM_IMPLEMENTATION`: likely custom implementation detected; reinvention signals exceed threshold.
- `MISSING`: repository appears eligible but no approved usage and no strong reinvention signal detected.
- `NOT_ELIGIBLE`: capability does not apply to this repository.
- `UNKNOWN`: insufficient evidence to classify.
- `EXEMPT`: repo has an approved exception on record; excluded from adoption rate denominator.

The `EXEMPT` status requires an entry in the catalog exceptions list (see section 9).

## 7. MVP Catalog

The MVP uses a single capability: **Platform HTTP Client** (`platform_http_client`), defined in `demo/catalog/catalog.yaml`.

This capability was chosen because HTTP client usage patterns are universal and immediately understandable to any engineering audience. The reinvention story (custom retry logic with `requests.Session`, `HTTPAdapter`, `urllib3.Retry`) is straightforward to demonstrate across the five synthetic demo repos.

The detection engine is catalog-driven and language-agnostic. Adding a second capability requires only a new YAML entry.

## 8. Versioning

The capability catalog must be versioned. Version is defined at the top of the catalog file:

```yaml
catalog_version: "1.0"
generated_at: "2026-05-31"
owner: platform-team
```

Each scan run records:

- `catalog_version` used during the scan.
- `capability_ids` included in the scan.
- `detection_rule_version` per capability.
- `scan_timestamp`.

When adoption results change between two scans of the same repos, the version metadata makes it clear whether the change was caused by a rule change or a repo change.

## 9. Exceptions

Some repositories have legitimate reasons to deviate from a platform capability. These should be recorded as approved exceptions, not counted as non-compliant.

Exceptions are defined in a separate `exceptions.yaml` file or as a top-level section in the catalog:

```yaml
exceptions:
  - repo_id: legacy-analytics-service
    capability_id: platform_http_client
    reason: "Pre-platform legacy service. Migration planned for Q3 2026."
    approved_by: platform-team
    approved_at: "2026-01-15"
    expires: "2026-09-30"

  - repo_id: security-tooling-service
    capability_id: platform_http_client
    reason: "Uses custom HTTP client required by InfoSec for mTLS handling."
    approved_by: infosec-team
    approved_at: "2026-03-01"
    expires: null   # no expiry; reviewed annually
```

Repos with valid, non-expired exceptions are classified as `EXEMPT` and excluded from the adoption rate denominator. Expired exceptions are treated as `MISSING` and flagged for follow-up.
