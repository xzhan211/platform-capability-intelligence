# Platform Capability Intelligence Architecture

## 1. Overview

The Platform Capability Intelligence application analyzes repositories across tenants to determine whether platform-provided building blocks are being adopted, bypassed, or reinvented.

The system is evidence-grounded and engineering-controlled. LLMs may interpret and synthesize signals, but every important claim must be supported by explicit evidence and pass validation before it appears in the final report.

## 2. Design Principles

1. **Capability-first, not repo-quality-first**
   - The core unit of analysis is a platform capability and its adoption across tenants.

2. **Evidence-grounded conclusions**
   - No adoption or reinvention claim should be made without evidence references.

3. **AI-assisted but engineering-controlled**
   - LLMs help classify ambiguous patterns and generate narrative insights, but deterministic rules and validators remain the source of control.

4. **Cross-repo visibility**
   - The application should aggregate signals across repositories and tenants, not only report findings inside one repo.

5. **Catalog-driven detection**
   - Platform capabilities must be explicitly defined in a versioned capability catalog.

6. **MVP simplicity with extensible architecture**
   - First version can use local repository upload and simple pattern rules, but the architecture should allow Bitbucket integration and enterprise metadata later.

## 3. High-Level Architecture

```text
Capability Catalog
        |
        v
Repo Source Adapter
(Local Upload first, Bitbucket later)
        |
        v
Workspace Manager
        |
        v
Capability Detection Engine
        |
        +--> Dependency Detector
        +--> Import / Package Detector
        +--> Config Detector
        +--> Template Detector
        +--> Code Pattern Detector
        +--> Optional LLM Classifier
        |
        v
Evidence Selector
        |
        v
Capability Usage Classifier
        |
        v
Cross-Repo Metrics Engine
        |
        v
LLM Insight Pipeline
        |
        v
Evaluator / Validator
        |
        v
Dashboard / Reports
```

## 4. Main Components

### 4.1 Capability Catalog

Defines the reusable platform capabilities and the detection rules used to identify adoption or reinvention.

See `capability_catalog.md`.

### 4.2 Repo Source Adapter

Fetches source code for analysis.

MVP:

- `LocalUploadSourceAdapter`: accepts uploaded repo archives.

Future:

- `BitbucketArchiveSourceAdapter`: downloads source archives from Bitbucket.
- `BitbucketCloneSourceAdapter`: clones repositories when git history or diff analysis is required.

### 4.3 Workspace Manager

Prepares a safe, temporary workspace for analysis.

Responsibilities:

- unpack uploaded repository archives;
- filter unsupported files;
- detect repository language and framework;
- extract dependency/config/build files;
- assign stable file IDs;
- clean up workspace after scan.

### 4.4 Capability Detection Engine

Runs two tiers of detection against the workspace: generic platform namespace detection and capability-specific detection.

#### Tier 1: PlatformNamespaceDetector (Generic)

Reads `platform_conventions` from the catalog top-level block. Detects any usage of the platform namespace without requiring per-capability entries. Produces a generic `USES_PLATFORM` signal per repo.

Covers capabilities that follow naming conventions. Does not require manual catalog entries for each capability.

#### Tier 2: Capability-Specific Detectors

Run per capability using catalog-defined rules and signal weights:

- **DependencyDetector**: scans `requirements.txt`, `setup.py`, `pyproject.toml`, `pom.xml`, `build.gradle` for approved/banned dependency patterns.
- **ImportDetector**: scans source imports for approved/banned package paths.
- **ConfigDetector**: scans YAML, `.env`, properties, JSON, and CI/CD files for approved/banned config keys.
- **TemplateDetector**: detects platform-provided CI/CD or deployment templates.
- **CodePatternDetector**: looks for class/function names and code structures that match anti-pattern rules in the catalog.
- **Optional LLM Classifier**: classifies ambiguous evidence only when deterministic rules produce UNKNOWN and further disambiguation is needed.

All detectors implement a language-agnostic interface: `Detector.detect(workspace, capability) -> DetectionSignal[]`. Adding Java detection means adding new implementations of the same interface.

### 4.5 Evidence Selector

Selects the most relevant evidence for each capability/repository pair.

This component is important because the LLM should not receive an unbounded dump of repository content.

MVP evidence selection priorities:

1. catalog-defined required files;
2. positive adoption signals;
3. reinvention signals;
4. missing expected patterns;
5. representative code snippets around detected patterns.

### 4.6 Capability Usage Classifier

Classifies each repository-capability pair using deterministic rules driven by signal weights from the capability catalog.

Valid statuses:

- `ADOPTED`: at least one high-weight adoption signal, or two or more medium-weight adoption signals.
- `CUSTOM_IMPLEMENTATION`: at least one high-weight reinvention signal, or two or more medium-weight reinvention signals; no high-weight adoption signal present.
- `MISSING`: repo is eligible but no adoption signals and reinvention signals are below threshold.
- `NOT_ELIGIBLE`: no eligibility rule matched.
- `UNKNOWN`: insufficient evidence for any determination.
- `EXEMPT`: repo has a valid, non-expired entry in the exceptions list. Excluded from adoption rate denominator. Shown separately in the dashboard.

Example for Snowflake Auth (Python repos):

```text
requirements.txt contains snowflake-connector-python (high-weight reinvention signal)
  AND no platform-snowflake-auth dependency
  AND SnowflakeTokenManager.py detected (high-weight reinvention signal)
  -> CUSTOM_IMPLEMENTATION / high confidence
```

### 4.7 Cross-Repo Metrics Engine and CrossRepoEvidenceSummary

Aggregates repository-level classifications into two outputs:

**CrossRepoMetric** (stored, displayed in dashboard):

- capability adoption rate (adopted eligible / total eligible; EXEMPT excluded from denominator);
- custom implementation count;
- missing adoption count;
- unknown count;
- exempt count;
- adoption trend over time (Phase 2, requires history).

**CrossRepoEvidenceSummary** (bounded structure passed to LLM pipeline):

- aggregate metrics;
- per-repo status + confidence + top evidence refs;
- common reinvention patterns across repos;
- unknowns list.

The CrossRepoEvidenceSummary is the only input passed to LLM steps. It is bounded by a token budget and assembled deterministically. See detection_pipeline.md Stage 10 for the full schema.

### 4.8 LLM Insight Pipeline

LLM is used for synthesis and narrative reporting. The pipeline is multi-step. LLM steps use Claude Bedrock structured output (tool use) to enforce schema. The final assembly is deterministic.

```text
CrossRepoEvidenceSummary (deterministic, bounded)
    -> SignalSummarizer (LLM, structured output)
    -> Hard gate validation (deterministic)
    -> InsightGenerator (LLM, structured output)
    -> Hard gate validation (deterministic)
    -> ReportAssembler (deterministic, no LLM)
```

LLM must not invent capabilities, repositories, tenant names, or usage patterns that do not appear in the CrossRepoEvidenceSummary.

Tool use reduces format failures. Semantic validation (evidence refs, capability IDs, repo IDs) is still enforced by the hard gate evaluator after each LLM step.

See detection_pipeline.md Stage 10 for full step-by-step input/output schemas.

### 4.9 Evaluator / Validator

Validates both deterministic classification and LLM-generated insights.

Hard checks:

- evidence references exist;
- file paths exist;
- capability IDs exist in catalog;
- repository IDs exist;
- adoption status is a valid enum;
- LLM claims are tied to evidence refs.

Soft checks:

- recommendation usefulness;
- unknowns coverage;
- cross-repo insight clarity;
- confidence level.

## 5. Data Model

### Capability

```text
capability_id
name
category
owner_team
status
maturity
documentation_url
catalog_version
```

### Repository

```text
repo_id
tenant_id
repo_name
source_type
branch
commit_sha
language_stack
last_scanned_at
```

### Tenant

```text
tenant_id
tenant_name
owner_group
platform_status
risk_tier optional
```

### CapabilityDetectionResult

```text
detection_id
scan_run_id
repo_id
tenant_id
capability_id
status: ADOPTED | CUSTOM_IMPLEMENTATION | MISSING | NOT_ELIGIBLE | UNKNOWN | EXEMPT
confidence: high | medium | low | unknown
rule_version
catalog_version
evidence_refs[]
unknowns[]
exempt_reason (populated when status = EXEMPT)
```

### EvidenceItem

```text
evidence_id
scan_run_id
repo_id
capability_id
source_type: dependency | import | config | code_snippet | template | llm_classification
file_path
line_start
line_end
content_summary
raw_content_pointer optional
```

### CrossRepoMetric

```text
metric_id
scan_batch_id
capability_id
metric_name
metric_value
eligible_repo_count
adopted_repo_count
custom_implementation_count
unknown_count
```

## 6. Deployment Modes

### MVP Local/Demo Mode

```text
CLI + local uploaded repo archives + local JSON/SQLite + Streamlit dashboard
```

### Service Mode

```text
FastAPI service + background worker + local or cloud storage
```

### Future AWS Mode

```text
FastAPI control plane + S3 + RDS/Postgres + ECS workers + optional Step Functions orchestration
```

Step Functions is not required for MVP. It becomes useful when the scan workflow grows into multiple long-running stages across many repositories.

## 7. Security Considerations

- Source code should remain inside approved internal environments.
- Repository archives should be encrypted at rest.
- Prompt inputs and outputs should be treated as sensitive.
- LLM calls must use approved internal/enterprise provider paths.
- Secrets should be filtered from evidence packages before LLM calls.
- Tenant access should be controlled through authorization rules.
- Audit logs should record who triggered scans and which repos were analyzed.

## 8. MVP Scope

MVP should support:

- multi-repo scan via `scan_manifest.yaml` + folder of archives (local upload);
- one capability in the catalog (specific capability TBD by team);
- Python repository detection (requirements.txt, imports, config files, class/function name patterns);
- manually maintained YAML capability catalog with signal weights;
- deterministic eligibility, adoption signal, and reinvention signal detection;
- evidence-backed classification: ADOPTED / CUSTOM_IMPLEMENTATION / MISSING / NOT_ELIGIBLE / UNKNOWN / EXEMPT;
- CrossRepoEvidenceSummary as bounded LLM input;
- LLM insight pipeline (SignalSummarizer → InsightGenerator → ReportAssembler) with hard gate validation;
- simple cross-repo adoption dashboard;
- evidence drill-down from classification to source evidence;
- exportable report.

The detector interfaces are language-agnostic. Adding Java detection in Phase 2 requires only new detector implementations, not architecture changes.

MVP should defer:

- Java detection;
- Bitbucket integration;
- git history/churn analysis;
- portfolio-scale multi-capability reporting;
- automated migration recommendations;
- policy enforcement or release gates;
- Backstage/developer portal integration;
- LLM-as-judge soft evaluation;
- exception/exempt UI management (data model supports it; UI deferred).
