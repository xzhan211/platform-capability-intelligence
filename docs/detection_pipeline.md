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

### MVP Input: Scan Manifest + Repo Archives

The MVP uses a `scan_manifest.yaml` file alongside a folder of repository archives.

```bash
platform-capability scan \
  --manifest ./demo-repos/scan_manifest.yaml \
  --catalog ./capabilities/catalog.yaml
```

#### scan_manifest.yaml format

```yaml
scan_batch_id: demo-batch-001
scan_timestamp: "2026-05-31T09:00:00Z"
catalog_version: "1.0"

repos:
  - repo_id: payment-service
    repo_name: payment-service
    tenant_id: payments-team
    archive: ./payment-service.zip
    branch: main
    commit_sha: null

  - repo_id: reporting-service
    repo_name: reporting-service
    tenant_id: analytics-team
    archive: ./reporting-service.zip
    branch: main
    commit_sha: null

  - repo_id: reconciliation-service
    repo_name: reconciliation-service
    tenant_id: finance-team
    archive: ./reconciliation-service.zip
    branch: main
    commit_sha: null
```

The manifest provides repo identity and tenant metadata without requiring a live Bitbucket connection. Each archive is a standard zip or tar.gz.

### Future Input

- Bitbucket archive download (V2): same manifest format, archive is downloaded automatically.
- Bitbucket clone (V3): shallow clone, enables diff scanning.
- Scheduled cross-repo scans: manifest is generated from an internal repo inventory API.

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

## 12. Stage 10: LLM Insight Pipeline (Multi-Step)

LLM is used to convert detected signals into readable platform insights. The pipeline uses three steps. LLM steps use Claude Bedrock structured output (tool use) to enforce schema. The final assembly is deterministic.

### Step 10.1: CrossRepoEvidenceSummary Assembly (Deterministic)

Before any LLM call, the CrossRepoAggregator builds a bounded, structured summary of all detection results. This is the only input the LLM receives — it never sees raw repository content or unbounded evidence dumps.

```json
{
  "capability_id": "snowflake_auth",
  "capability_name": "Snowflake Authentication",
  "catalog_version": "1.0",
  "scan_batch_id": "demo-batch-001",
  "aggregate_metrics": {
    "eligible_repo_count": 4,
    "adopted_count": 1,
    "custom_implementation_count": 1,
    "missing_count": 1,
    "unknown_count": 1,
    "exempt_count": 0,
    "adoption_rate": 0.25
  },
  "repo_summaries": [
    {
      "repo_id": "payment-service",
      "tenant_id": "payments-team",
      "status": "ADOPTED",
      "confidence": "high",
      "top_evidence_refs": ["ev-001", "ev-002"]
    },
    {
      "repo_id": "reporting-service",
      "tenant_id": "analytics-team",
      "status": "CUSTOM_IMPLEMENTATION",
      "confidence": "high",
      "top_evidence_refs": ["ev-010", "ev-011", "ev-012"]
    }
  ],
  "common_reinvention_patterns": [
    "snowflake-connector-python used without platform wrapper",
    "SnowflakeTokenManager class detected"
  ],
  "unknowns": [
    "legacy-analytics-service: insufficient evidence, possible custom auth in legacy module"
  ]
}
```

The token budget for the CrossRepoEvidenceSummary is enforced before the LLM call. If the summary exceeds the budget, lower-confidence evidence items are dropped first.

### Step 10.2: SignalSummarizer (LLM, Structured Output)

Input: CrossRepoEvidenceSummary + capability catalog entry.

The LLM produces a structured per-capability signal summary.

Output schema (enforced via tool use):

```json
{
  "capability_id": "snowflake_auth",
  "adoption_pattern_summary": "One repo uses the approved platform dependency and import. Three eligible repos do not use the approved capability.",
  "reinvention_pattern_summary": "One repo uses snowflake-connector-python directly with a custom SnowflakeTokenManager class.",
  "evidence_refs": ["ev-010", "ev-011"],
  "unknowns": ["legacy-analytics-service: classification unclear"],
  "confidence": "high"
}
```

Hard gate check after this step: all evidence_refs must exist, capability_id must exist in catalog.

### Step 10.3: InsightGenerator (LLM, Structured Output)

Input: validated SignalSummarizer output + aggregate metrics.

The LLM produces cross-repo platform-level insights and actionable recommendations.

Output schema (enforced via tool use):

```json
{
  "insight_summary": "The Snowflake Auth capability has a 25% adoption rate among eligible repos. One repo implements custom authentication, suggesting onboarding friction for batch-style Snowflake integrations.",
  "recommendations": [
    {
      "recommendation_id": "rec-001",
      "priority": "high",
      "target": "reporting-service",
      "action": "Migrate SnowflakeTokenManager to the platform-snowflake-auth library.",
      "evidence_refs": ["ev-010", "ev-011"]
    },
    {
      "recommendation_id": "rec-002",
      "priority": "medium",
      "target": "platform-team",
      "action": "Add a batch-job integration example to Snowflake Auth documentation.",
      "evidence_refs": ["ev-010"]
    }
  ],
  "unknowns": ["legacy-analytics-service: follow up required to determine auth pattern"]
}
```

Hard gate check after this step: all evidence_refs exist, all repo_ids cited exist in the scan batch, capability_ids exist in catalog, no unsupported claims.

### Step 10.4: ReportAssembler (Deterministic)

Assembles the final report from validated SignalSummarizer and InsightGenerator outputs.

- attaches all validated evidence refs;
- records catalog version, prompt versions, model IDs, LLM usage metadata;
- produces `FinalReport` for the evaluator;
- no LLM is called in this step.

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
