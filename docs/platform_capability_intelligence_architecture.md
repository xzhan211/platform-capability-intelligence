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
Capability Catalog (YAML)
        |
        v
Scan Manifest (YAML) ──► ScanPipeline (pipeline/scan_pipeline.py)
        |
        v
WorkspaceManager              (workspace/manager.py)
  unpack archive, file inventory, language detection
        |
        v
Four Detectors per capability:
  DependencyDetector          (detectors/dependency.py)
  ImportDetector              (detectors/import_detector.py)
  CodePatternDetector         (detectors/code_pattern.py)
  PlatformNamespaceDetector   (detectors/namespace.py)  ← Tier 1 generic
        |
        v  DetectionSignal[] + EvidenceItem[]
        |
        v
CapabilityUsageClassifier     (classification/classifier.py)
  deterministic, signal-weight rules
  → ADOPTED | CUSTOM_IMPLEMENTATION | MISSING | NOT_ELIGIBLE | UNKNOWN | EXEMPT
        |
        v
CrossRepoAggregator           (classification/aggregator.py)
  → CrossRepoMetric + CrossRepoEvidenceSummary (bounded LLM input)
        |
        v
LLMPipeline                   (llm/pipeline.py)
  SignalSummarizer  (llm/mock_client.py or bedrock)
      ↓ hard gate check (evidence refs, capability IDs)
  InsightGenerator  (llm/mock_client.py or bedrock)
      ↓ hard gate check (evidence refs, repo IDs, no hallucinations)
  ReportAssembler   (deterministic, no LLM)
        |
        v
FinalReport (JSON)            (models.py → output/<batch>.json)
        |
        v
Streamlit Dashboard           (dashboard/app.py)
```

## 3a. Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.11 |
| Package manager | uv (lockfile: `uv.lock`) |
| Models | Pydantic v2 |
| Catalog / manifest | PyYAML |
| CLI | Click + Rich |
| Dashboard | Streamlit |
| LLM (default) | Mock client (no credentials needed) |
| LLM (production) | AWS Bedrock — Claude 3.5 Sonnet |
| Tests | pytest + pytest-cov (82% coverage) |

## 4. Main Components

### 4.1 Capability Catalog

Defines the reusable platform capabilities and the detection rules used to identify adoption or reinvention.

See `capability_catalog.md`.

#### How the catalog is populated

The app only knows what platform capabilities exist if they are registered in the catalog. There are three paths:

**MVP — Manual YAML**: The platform team writes `catalog.yaml` directly. Required for anti-patterns and eligibility rules in all versions. Status `draft` entries are excluded from scoring until reviewed and promoted.

**Phase 2 — CatalogBootstrapper**: A utility that queries the internal artifact registry (Artifactory, private PyPI, internal Maven) to discover platform-published packages and auto-generates skeleton catalog entries with adoption signals pre-filled. Anti-patterns and eligibility rules still require human completion. Entries start as `draft` and are activated by the platform team.

**Phase 2 — Developer Portal Import**: If the organization uses Backstage, Cortex, OpsLevel, or a similar internal developer portal, catalog metadata can be imported from there, reducing duplication.

The `source` field on each capability entry (`manual | auto_generated | imported`) tracks how it was created.

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

- **DependencyDetector**: scans `requirements.txt`, `setup.py`, `pyproject.toml` for approved/banned dependency patterns.
- **ImportDetector**: scans Python import statements for approved/banned package paths.
- **CodePatternDetector**: looks for class/function names and code structures that match anti-pattern rules in the catalog.

Deferred to Phase 2:

- **ConfigDetector**: will scan YAML, `.env`, properties, JSON, and CI/CD files for approved/banned config keys.
- **TemplateDetector**: will detect platform-provided CI/CD or deployment templates.
- **Optional LLM Classifier**: will classify ambiguous evidence only when deterministic rules produce UNKNOWN and further disambiguation is needed.

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

### RepoDefinition (scan input)

```text
repo_id
repo_name
tenant_id
archive          : path to zip or tar.gz archive
branch           : default "main"
commit_sha       : optional
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
exempt_reason    : populated when status = EXEMPT
adoption_signals[]
reinvention_signals[]
```

### EvidenceItem

All evidence items are stored in `models.py` and serialized to the `FinalReport` JSON.

```text
evidence_id          : stable hash-based ID
scan_run_id
repo_id
capability_id
source_type          : dependency | import | code_snippet | generic_platform
file_path
line_start           : optional
line_end             : optional
content_summary      : human-readable description of what was detected
raw_content          : the matching text (snippet, dependency line, import statement)
```

### CrossRepoMetric

```text
metric_id
scan_batch_id
capability_id
eligible_repo_count  : excludes NOT_ELIGIBLE and EXEMPT
adopted_count
custom_implementation_count
missing_count
unknown_count
exempt_count
not_eligible_count
adoption_rate        : adopted_count / eligible_repo_count
```

## 6. Deployment Modes

### Current: Local CLI + Dashboard

```bash
# Install
uv sync

# Run scan
uv run platform-capability scan --manifest demo/manifest/scan_manifest.yaml --catalog demo/catalog/catalog.yaml

# Run dashboard
uv run streamlit run dashboard/app.py
```

Output is written to `./output/report-<scan_batch_id>.json`. No database required — everything is plain JSON files.

### Future: Service Mode

```text
FastAPI control plane + background worker + cloud storage (S3) + RDS/Postgres
```

### Future: AWS Production Mode

```text
FastAPI API + S3 artifact storage + RDS Postgres + ECS Fargate workers + optional Step Functions orchestration + Bedrock LLM
```

## 7. Security Considerations

- Repository archives should be treated as sensitive source code.
- Temporary workspaces are cleaned up after each scan (`WorkspaceManager.cleanup()`).
- LLM calls should use approved internal/enterprise provider paths (Bedrock recommended for bank environments).
- Secrets and credentials in source files should be redacted before inclusion in evidence snippets.
- Audit logs should record who triggered scans and which repos were analyzed.

## 8. What Is Built (v0.1.0)

Implemented and tested:

- multi-repo scan via `scan_manifest.yaml` + zip archives;
- `platform_http_client` as the demo capability (Python repos);
- four detectors: DependencyDetector, ImportDetector, CodePatternDetector, PlatformNamespaceDetector;
- deterministic classification: ADOPTED / CUSTOM_IMPLEMENTATION / MISSING / NOT_ELIGIBLE / UNKNOWN / EXEMPT;
- `CrossRepoAggregator` + `CrossRepoEvidenceSummary`;
- mock LLM pipeline (SignalSummarizer → InsightGenerator → ReportAssembler);
- hard gate evaluator with retry and fallback in `llm/pipeline.py`;
- five-page Streamlit dashboard;
- CLI (`platform-capability scan`, `platform-capability show`);
- 104 unit tests, 82% coverage;
- `uv` for package management with `uv.lock`.

Deferred to Phase 2:

- Java detection (interfaces are language-agnostic; add new detector implementations);
- Bitbucket source adapter;
- additional capabilities in catalog;
- churn × complexity temporal signal;
- Backstage/developer portal integration;
- LLM-as-judge soft evaluation;
- exception/exempt management UI;
- FastAPI service mode;
- AWS production deployment.
