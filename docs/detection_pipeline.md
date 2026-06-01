# Detection Pipeline

## 1. Purpose

The detection pipeline determines whether repositories are adopting, missing, or reinventing platform capabilities.

The pipeline should be deterministic first, LLM-assisted second. LLMs should only interpret selected evidence and ambiguous patterns. They should not replace explicit catalog rules.

## 2. Pipeline Overview

```text
Input Repositories
    -> Workspace Preparation
    -> Capability Catalog Load
    -> Eligibility Detection
    -> Adoption Signal Detection
    -> Reinvention Signal Detection
    -> Evidence Selection
    -> Capability Usage Classification
    -> Cross-Repo Aggregation
    -> LLM Insight Generation
    -> Validation / Evaluation
    -> Dashboard / Report
```

## 3. Stage 1: Input Repositories

MVP input:

- local uploaded repo archive;
- optional metadata file mapping repo to tenant.

Future input:

- Bitbucket archive download;
- Bitbucket clone;
- scheduled cross-repo scans;
- repository metadata from internal inventory systems.

Required metadata:

```text
repo_id
repo_name
tenant_id
source_type
branch optional
commit_sha optional
scan_timestamp
```

## 4. Stage 2: Workspace Preparation

Responsibilities:

- unpack archive;
- detect languages and frameworks;
- collect file tree;
- extract dependency/config/build files;
- ignore generated and binary files;
- assign stable file IDs.

Suggested ignored paths:

```text
.git/
target/
build/
dist/
node_modules/
.venv/
__pycache__/
.idea/
.vscode/
```

## 5. Stage 3: Capability Catalog Load

The system loads a versioned capability catalog.

Each capability definition provides:

- eligibility rules;
- adoption patterns;
- reinvention anti-patterns;
- evidence collection rules;
- minimum evidence requirements.

The scan result must record the catalog version used.

## 6. Stage 4: Eligibility Detection

Before calculating adoption, determine whether the capability applies to the repo.

Example for Snowflake authentication:

A repository is eligible if it has any of:

- Snowflake JDBC dependency;
- Snowflake config keys;
- files/classes with `Snowflake` in name;
- SQL warehouse configuration;
- existing Snowflake connection code.

If a repo is not eligible, it should not count against adoption rate.

Classification output:

```text
repo_id
capability_id
eligibility_status: ELIGIBLE | NOT_ELIGIBLE | UNKNOWN
eligibility_evidence_refs[]
```

## 7. Stage 5: Adoption Signal Detection

Detect approved platform usage.

Signal examples:

- approved dependency exists;
- approved import exists;
- approved configuration is present;
- platform template is referenced;
- approved client API is used.

For Snowflake authentication:

```text
Dependency: com.company.platform:snowflake-auth
Import: com.company.platform.snowflake.SnowflakeAuthClient
Config: platform.snowflake.auth.enabled=true
```

Output:

```text
AdoptionSignal
- signal_id
- repo_id
- capability_id
- signal_type
- evidence_ref
- confidence
```

## 8. Stage 6: Reinvention Signal Detection

Detect custom implementations that appear to duplicate platform-provided capabilities.

Signal examples:

- direct use of low-level third-party dependency without platform wrapper;
- custom class names similar to platform implementation;
- custom token refresh/authentication logic;
- repeated integration code across repositories;
- custom CI/CD logic when standard templates exist.

For Snowflake authentication:

```text
- net.snowflake:snowflake-jdbc exists
- platform-snowflake-auth is missing
- SnowflakeTokenManager.java exists
- OAuth token refresh logic detected
```

Output:

```text
ReinventionSignal
- signal_id
- repo_id
- capability_id
- signal_type
- evidence_ref
- confidence
```

## 9. Stage 7: Evidence Selection

Evidence selection prepares bounded evidence for classification and LLM synthesis.

Evidence types:

- dependency entries;
- imports;
- config keys;
- file names;
- selected code snippets;
- template references;
- README or onboarding references.

MVP rules:

1. Always include evidence required by the capability catalog.
2. Prioritize adoption and reinvention signals.
3. Include short code snippets around detected patterns.
4. Enforce token budget before LLM call.
5. Assign evidence IDs to every evidence item.

Evidence item example:

```json
{
  "evidence_id": "ev-snowflake-001",
  "repo_id": "payment-service",
  "capability_id": "snowflake_auth",
  "source_type": "dependency",
  "file_path": "pom.xml",
  "content_summary": "net.snowflake:snowflake-jdbc dependency detected"
}
```

## 10. Stage 8: Capability Usage Classification

Classify each repository-capability pair.

Recommended deterministic rules:

```text
If NOT_ELIGIBLE:
  status = NOT_ELIGIBLE

If approved adoption signal exists:
  status = ADOPTED

If eligible and reinvention signals exceed threshold:
  status = CUSTOM_IMPLEMENTATION

If eligible and no adoption signal exists:
  status = MISSING

If evidence is insufficient:
  status = UNKNOWN
```

Each classification must include:

- status;
- confidence;
- evidence refs;
- unknowns;
- rule version.

## 11. Stage 9: Cross-Repo Aggregation

Aggregate repository classifications into cross-repo metrics.

Example metrics:

```text
Capability Adoption Rate = adopted eligible repos / eligible repos
Custom Implementation Rate = custom implementation repos / eligible repos
Missing Adoption Rate = missing repos / eligible repos
Unknown Rate = unknown repos / total scanned repos
Tenant Capability Coverage = adopted recommended capabilities / eligible recommended capabilities
```

Example output:

```text
Snowflake Auth
- 10 eligible repos
- 6 adopted
- 3 custom implementations
- 1 unknown
- adoption rate: 60%
```

## 12. Stage 10: LLM Insight Generation

LLM is used to convert detected signals into readable platform insights.

Recommended MVP LLM steps:

### 10.1 SignalSummarizer

Summarizes evidence for each capability.

Input:

- capability catalog entry;
- detection results;
- evidence refs;
- cross-repo metrics.

Output:

- concise capability summary;
- adoption pattern;
- reinvention pattern;
- unknowns.

### 10.2 InsightGenerator

Generates platform-level insights and recommendations.

Example output:

```text
Three eligible repositories appear to implement custom Snowflake authentication instead of using the platform capability. The strongest common pattern is direct use of Snowflake JDBC combined with custom token refresh logic. This suggests the platform Snowflake auth capability may need better onboarding documentation or migration examples.
```

### 10.3 ReportAssembler

Deterministically assembles the final report.

LLM text should be included only if:

- evidence refs are valid;
- capability IDs exist;
- repo IDs exist;
- no unsupported claims are detected.

## 13. Stage 11: Evaluation

See `evaluation.md`.

## 14. Stage 12: Dashboard

Recommended MVP dashboard sections:

1. Capability overview
2. Adoption by capability
3. Tenant/repo matrix
4. Reimplementation signals
5. Evidence drill-down
6. LLM-generated insight with validation status
7. Recommended platform actions

## 15. Example End-to-End Scenario

Capability: Snowflake Authentication

Input:

- 5 tenant repositories
- capability catalog entry for Snowflake authentication

Detection:

- Repo A uses approved platform dependency -> ADOPTED
- Repo B uses approved platform dependency -> ADOPTED
- Repo C uses Snowflake JDBC and custom token refresh -> CUSTOM_IMPLEMENTATION
- Repo D has Snowflake config but no approved usage -> MISSING
- Repo E has no Snowflake usage -> NOT_ELIGIBLE

Output:

```text
Snowflake Auth Adoption:
- Eligible repos: 4
- Adopted: 2
- Custom implementation: 1
- Missing: 1
- Not eligible: 1

Recommendation:
- Provide a migration guide for repos using direct Snowflake JDBC.
- Add a sample batch-job integration template.
- Follow up with tenant owning Repo C due to custom auth implementation.
```
