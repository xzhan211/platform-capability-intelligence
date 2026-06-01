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

Runs deterministic and optional semantic detectors against the workspace using catalog rules.

Detector types:

- dependency detector: scans `pom.xml`, `build.gradle`, `requirements.txt`, etc.;
- import detector: scans source imports and packages;
- config detector: scans YAML, properties, JSON, Terraform, and CI/CD files;
- template detector: detects platform-provided templates;
- code pattern detector: looks for class/function names and code structures that suggest custom implementations;
- optional LLM classifier: classifies ambiguous evidence only when deterministic rules are insufficient.

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

Classifies each repository-capability pair into one of:

- `ADOPTED`
- `CUSTOM_IMPLEMENTATION`
- `MISSING`
- `NOT_ELIGIBLE`
- `UNKNOWN`

MVP classification should be primarily deterministic.

Example:

```text
If repo uses net.snowflake:snowflake-jdbc and does not use platform-snowflake-auth,
and custom token refresh logic is detected, classify as CUSTOM_IMPLEMENTATION.
```

### 4.7 Cross-Repo Metrics Engine

Aggregates repository-level classification into platform-level metrics:

- capability adoption rate;
- eligible tenant coverage;
- custom implementation count;
- missing adoption count;
- adoption trend over time;
- tenant capability coverage;
- platform stickiness indicators.

### 4.8 LLM Insight Pipeline

LLM is used for synthesis, ambiguity resolution, and narrative reporting.

Recommended MVP pipeline:

```text
SignalSummarizer
    -> Converts detected evidence into capability-level summaries.

InsightGenerator
    -> Generates cross-repo insights and recommendations.

ReportAssembler
    -> Deterministically assembles the final report with evidence refs.
```

LLM must not invent capabilities, repositories, tenant names, or usage patterns that do not appear in the evidence package.

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
status: ADOPTED | CUSTOM_IMPLEMENTATION | MISSING | NOT_ELIGIBLE | UNKNOWN
confidence
rule_version
evidence_refs[]
unknowns[]
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

- local repo archive upload;
- small capability catalog;
- one or two capabilities, preferably Snowflake authentication first;
- deterministic detection rules;
- evidence-backed classification;
- simple cross-repo adoption dashboard;
- LLM-generated insight with evidence validation;
- exportable report.

MVP should defer:

- Bitbucket integration;
- git history/churn analysis;
- portfolio-scale reporting;
- automated migration recommendations;
- policy enforcement;
- release gates;
- full enterprise scanner integration.
