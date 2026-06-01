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

Example: A service with no Snowflake access should not lower the adoption rate of Snowflake authentication.

## 3. Capability Catalog Schema

Suggested YAML representation (Python-first example):

```yaml
capability_id: snowflake_auth
name: Snowflake Authentication
category: data_integration
owner_team: platform-data
status: stable
maturity: stable
catalog_version: "1.0"
description: Standard platform capability for authenticating to Snowflake.
documentation_url: https://internal/docs/snowflake-auth
recommended_for:
  - services that read from or write to Snowflake

approved_usage_patterns:
  dependencies:
    - pattern: "platform-snowflake-auth"
      weight: high        # sufficient alone to classify ADOPTED
  imports:
    - pattern: "platform.snowflake.auth.SnowflakeAuthClient"
      weight: high
    - pattern: "platform.snowflake.credentials"
      weight: medium      # corroborating signal, not sufficient alone
  config_keys:
    - pattern: "platform.snowflake.auth.enabled"
      weight: high
    - pattern: "platform.snowflake.role"
      weight: medium
  templates:
    - pattern: "platform-snowflake-batch-template"
      weight: medium

anti_patterns:
  class_name_patterns:
    - pattern: "SnowflakeTokenManager"
      weight: high        # sufficient alone to flag CUSTOM_IMPLEMENTATION
    - pattern: "SnowflakeCredentialRefresher"
      weight: high
    - pattern: "CustomSnowflakeAuth"
      weight: high
    - pattern: "*snowflake*auth*"   # case-insensitive wildcard
      weight: medium
  dependency_patterns:
    - pattern: "snowflake-connector-python"
      note: "raw Snowflake driver without platform wrapper"
      weight: high
  code_patterns:
    - pattern: "snowflake.connector.connect"
      note: "direct low-level Snowflake connection"
      weight: high
    - pattern: "token_refresh"
      note: "custom token refresh logic near Snowflake usage"
      weight: medium

eligibility_rules:
  include_if:
    - dependency: "snowflake-connector-python"
    - dependency: "platform-snowflake-auth"
    - config_key_prefix: "snowflake"
    - file_name_pattern: "*snowflake*"
    - import_prefix: "snowflake"

evidence_rules:
  collect_files:
    - "requirements.txt"
    - "setup.py"
    - "pyproject.toml"
    - "*.cfg"
    - "*.yaml"
    - "*.env"
    - "*snowflake*.py"
    - "*auth*.py"
  max_snippet_lines: 40

minimum_evidence_required:
  adoption: 1              # at least 1 high-weight adoption signal
  reinvention: 1           # at least 1 high-weight OR 2+ medium-weight signals
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

- `draft`: proposed capability, not ready for tenant adoption;
- `beta`: available to early adopters;
- `stable`: recommended for broad adoption;
- `deprecated`: should not be adopted by new tenants;
- `retired`: no longer supported.

Only `beta` and `stable` capabilities should normally be included in adoption scoring.

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

For the first demo, keep the catalog intentionally small: one capability.

The specific capability (e.g., Snowflake authentication, logging wrapper, platform auth) should be chosen based on which one provides the clearest adoption/reinvention story with the demo repos.

The detection engine is catalog-driven and language-agnostic. Switching the MVP capability only requires updating the YAML catalog and the synthetic demo repos.

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
    capability_id: snowflake_auth
    reason: "Pre-platform legacy service. Migration planned for Q3 2026."
    approved_by: platform-team
    approved_at: "2026-01-15"
    expires: "2026-09-30"

  - repo_id: security-tooling-service
    capability_id: snowflake_auth
    reason: "Uses custom auth required by InfoSec for privileged access."
    approved_by: infosec-team
    approved_at: "2026-03-01"
    expires: null   # no expiry; reviewed annually
```

Repos with valid, non-expired exceptions are classified as `EXEMPT` and excluded from the adoption rate denominator. Expired exceptions are treated as `MISSING` and flagged for follow-up.
