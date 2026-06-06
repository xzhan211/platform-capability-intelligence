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

Ignored paths (from `config.py` `ignored_dirs`):

```text
.git/
__pycache__/
.venv/
venv/
env/
node_modules/
build/
dist/
target/
.idea/
.vscode/
.mypy_cache/
.pytest_cache/
.ruff_cache/
```

## 5. Stage 3: Capability Catalog Load

The system loads a versioned capability catalog.

The catalog has two sections:

**Top-level `platform_conventions` block (optional, Tier 1):**

Defines generic platform namespace rules that apply across all repos without per-capability entries:

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

If present, the `PlatformNamespaceDetector` runs against all repos and produces generic `USES_PLATFORM` signals. This provides breadth visibility — "which repos use the platform at all" — without requiring any per-capability catalog work.

**Per-capability entries (Tier 2):**

Each capability definition provides:

- eligibility rules;
- adoption patterns with signal weights;
- reinvention anti-patterns with signal weights;
- evidence collection rules;
- minimum evidence requirements.

Reinvention anti-patterns always require manual curation. They cannot be auto-derived.

The scan result must record the catalog version and whether `platform_conventions` was active.

## 6. Stage 4: Eligibility Detection

Before calculating adoption, the `CapabilityUsageClassifier` determines whether the capability applies to the repo by checking the `eligibility_rules` block from the catalog against the workspace content.

Example for Platform HTTP Client:

A repository is eligible if any of these match:
- `requests`, `httpx`, `aiohttp`, or `platform-http-client` found in dependency files
- an import statement starting with `requests`, `httpx`, or `platform_http_client`

Repos with no HTTP-related dependencies (e.g., a pure notification service using only `boto3`) are classified `NOT_ELIGIBLE` and excluded from the adoption rate denominator.

Eligibility is evaluated inside the classifier (`classification/classifier.py`, `_is_eligible()`). There is no separate eligibility stage — it is the first check inside `classify()`.

## 7. Stage 5: Adoption Signal Detection

The four detectors run against the workspace and return `DetectionSignal` objects. Each signal has a `signal_type` (adoption or reinvention) and a `weight` (high, medium, low) from the catalog definition.

**DependencyDetector** — scans `requirements.txt`, `setup.py`, `pyproject.toml`:

```text
platform-http-client==2.1.0  →  ADOPTION / high
```

**ImportDetector** — scans Python import statements:

```text
from platform_http_client import PlatformHttpClient  →  ADOPTION / high
import platform_http_client                          →  ADOPTION / medium
```

**CodePatternDetector** — scans class/function names and inline code:

```text
class RetrySession(requests.Session):  →  REINVENTION / high
HTTPAdapter(max_retries=...)           →  REINVENTION / high
```

**PlatformNamespaceDetector** — generic prefix matching from `platform_conventions` block (Tier 1):

```text
from platform_http_client import ...  →  GENERIC_PLATFORM / medium
platform-http-client in requirements  →  GENERIC_PLATFORM / medium
```

Each signal carries an `evidence_ref` pointing to the `EvidenceItem` that triggered it.

## 8. Stage 6: Reinvention Signal Detection

Reinvention signals are produced by the same four detectors when they match `anti_patterns` from the catalog. Examples for Platform HTTP Client:

```text
requests==2.31.0 in requirements.txt        →  REINVENTION / medium (raw requests)
class RetrySession(requests.Session)        →  REINVENTION / high   (custom session)
from requests.adapters import HTTPAdapter   →  REINVENTION / high   (manual retry)
Retry(total=3, backoff_factor=0.5)          →  REINVENTION / high   (manual retry)
```

All signals are returned as `DetectionSignal` objects with a stable `evidence_ref` pointing to the collected `EvidenceItem`.

## 9. Stage 7: Evidence Selection

Evidence items are collected by the detectors and stored in a dict keyed by `evidence_id`. The `CrossRepoAggregator` selects the top items per repo for inclusion in the `CrossRepoEvidenceSummary` (the bounded LLM input).

Evidence item structure (from `models.py`):

```json
{
  "evidence_id": "ev-dep-reinv-a1b2c3d4",
  "scan_run_id": "run-abc123",
  "repo_id": "reporting-service",
  "capability_id": "platform_http_client",
  "source_type": "dependency",
  "file_path": "requirements.txt",
  "line_start": null,
  "content_summary": "Reinvention dependency 'requests' found in requirements.txt",
  "raw_content": "requests"
}
```

`source_type` values: `dependency`, `import`, `code_snippet`, `generic_platform`.

## 10. Stage 8: Capability Usage Classification

The `CapabilityUsageClassifier.classify()` applies deterministic signal weight rules from the catalog:

```text
Check EXEMPT first:
  → If repo_id + capability_id match a valid, non-expired catalog exception → EXEMPT

Check NOT_ELIGIBLE:
  → If _is_eligible() returns False → NOT_ELIGIBLE

Separate signals by type:
  adoption_signals  = [s for s in signals if s.signal_type == ADOPTION]
  reinvention_signals = [s for s in signals if s.signal_type == REINVENTION]

ADOPTED:
  → high_adopt >= 1  OR  med_adopt >= 2

CUSTOM_IMPLEMENTATION:
  → (high_reinv >= 1  OR  med_reinv >= 2)  AND  high_adopt == 0

MISSING:
  → no adoption signals  AND  high_reinv == 0  AND  med_reinv < 2

UNKNOWN:
  → everything else (insufficient evidence)
```

Each result includes `status`, `confidence`, `evidence_refs`, `unknowns`, and `catalog_version`.

## 11. Stage 9: Cross-Repo Aggregation

The `CrossRepoAggregator.aggregate()` produces two outputs:

**`CrossRepoMetric`** (stored, displayed in dashboard):

```text
Platform HTTP Client — demo-batch-001
  eligible_repo_count    : 4
  adopted_count          : 1
  custom_implementation  : 2
  missing_count          : 1
  unknown_count          : 0
  exempt_count           : 0
  not_eligible_count     : 1
  adoption_rate          : 0.25  (adopted / eligible; EXEMPT excluded)
```

**`CrossRepoEvidenceSummary`** (bounded structure, passed to LLM pipeline):

- aggregate metrics
- per-repo status + confidence + top 3 evidence refs
- common reinvention patterns extracted across repos
- unknowns list
- token count estimate

## 12. Stage 10: LLM Insight Pipeline (Multi-Step)

LLM is used to convert detected signals into readable platform insights. The pipeline uses three steps. LLM steps use Claude Bedrock structured output (tool use) to enforce schema. The final assembly is deterministic.

### Step 10.1: CrossRepoEvidenceSummary Assembly (Deterministic)

Before any LLM call, the CrossRepoAggregator builds a bounded, structured summary of all detection results. This is the only input the LLM receives — it never sees raw repository content or unbounded evidence dumps.

```json
{
  "capability_id": "platform_http_client",
  "capability_name": "Platform HTTP Client",
  "catalog_version": "1.0",
  "scan_batch_id": "demo-batch-001",
  "aggregate_metrics": {
    "eligible_repo_count": 4,
    "adopted_count": 1,
    "custom_implementation_count": 2,
    "missing_count": 1,
    "unknown_count": 0,
    "exempt_count": 0,
    "adoption_rate": 0.25
  },
  "repo_summaries": [
    {
      "repo_id": "payment-service",
      "tenant_id": "payments-team",
      "status": "ADOPTED",
      "confidence": "high",
      "top_evidence_refs": ["ev-dep-adopt-a1b2", "ev-imp-adopt-c3d4"],
      "key_findings": ["Adoption: Approved dependency: platform-http-client"]
    },
    {
      "repo_id": "reporting-service",
      "tenant_id": "analytics-team",
      "status": "CUSTOM_IMPLEMENTATION",
      "confidence": "high",
      "top_evidence_refs": ["ev-cls-e5f6", "ev-code-g7h8"],
      "key_findings": ["Reinvention: Custom class: RetrySession", "Reinvention: Code pattern: HTTPAdapter"]
    }
  ],
  "common_reinvention_patterns": [
    "Reinvention dependency: requests (Raw requests library without platform wrapper)",
    "Reinvention: Custom class: RetrySession"
  ],
  "unknowns": []
}
```

The token budget for the CrossRepoEvidenceSummary is enforced before the LLM call. If the summary exceeds the budget, lower-confidence evidence items are dropped first.

### Step 10.2: SignalSummarizer (LLM)

Implemented in `llm/mock_client.py` (`summarize_signals()`) and orchestrated by `llm/pipeline.py`.

Input: `CrossRepoEvidenceSummary` (bounded, deterministically assembled).

The LLM produces a `SignalSummarizerOutput`:

```json
{
  "capability_id": "platform_http_client",
  "adoption_pattern_summary": "1 repo uses the approved platform-http-client dependency and PlatformHttpClient import.",
  "reinvention_pattern_summary": "2 repos implement custom HTTP handling: reporting-service has a RetrySession class; legacy-analytics-service uses both requests and httpx without a platform wrapper.",
  "evidence_refs": ["ev-dep-adopt-a1b2", "ev-dep-reinv-c3d4"],
  "unknowns": [],
  "confidence": "high"
}
```

Hard gate check (in `llm/pipeline.py`): all `evidence_refs` must exist in the evidence package; `capability_id` must exist in catalog. Invalid refs are stripped; the check does not retry for stripped refs.

### Step 10.3: InsightGenerator (LLM)

Implemented in `llm/mock_client.py` (`generate_insights()`) and orchestrated by `llm/pipeline.py`.

Input: validated `SignalSummarizerOutput` + aggregate metrics text.

The LLM produces an `InsightGeneratorOutput`:

```json
{
  "insight_summary": "The Platform HTTP Client capability has a 25% adoption rate among 4 eligible repos. 2 repos implement custom alternatives (reporting-service, legacy-analytics-service). Platform team should prioritize outreach to repos with custom implementations.",
  "recommendations": [
    {
      "recommendation_id": "rec-a1b2c3",
      "priority": "high",
      "target": "reporting-service",
      "action": "Migrate custom RetrySession to platform-http-client. Contact the analytics-team to schedule migration.",
      "evidence_refs": ["ev-cls-d4e5f6"]
    },
    {
      "recommendation_id": "rec-g7h8i9",
      "priority": "medium",
      "target": "platform-team",
      "action": "Add a migration guide for teams currently using raw requests.",
      "evidence_refs": []
    }
  ],
  "unknowns": []
}
```

Hard gate check: all `evidence_refs` must exist; all `target` values must be a valid `repo_id` from the scan batch or the literal string `"platform-team"`. Hallucinated targets are flagged as warnings and stripped.

### Step 10.4: ReportAssembler (Deterministic)

Assembles the final report from validated SignalSummarizer and InsightGenerator outputs.

- attaches all validated evidence refs;
- records catalog version, prompt versions, model IDs, LLM usage metadata;
- produces `FinalReport` for the evaluator;
- no LLM is called in this step.

### Retry Flow Between Steps

Each LLM step (SignalSummarizer, InsightGenerator) is followed by a hard gate check. If the check fails, a targeted repair prompt is sent before retrying. The deterministic report is always available as a fallback.

```text
SignalSummarizer (LLM)
    -> Hard Gate Check
        PASS -> continue to InsightGenerator
        FAIL -> Grounding/Schema Repair Prompt -> retry (max 2)
            Still FAIL -> skip InsightGenerator
                       -> ReportAssembler uses deterministic-only data
                       -> final_status = FAILED_FALLBACK_TO_DETERMINISTIC

InsightGenerator (LLM)
    -> Hard Gate Check
        PASS -> ReportAssembler
        FAIL -> Grounding/Schema Repair Prompt -> retry (max 2)
            Still FAIL -> ReportAssembler uses SignalSummarizer output only
                       -> final_status = ACCEPTED_WITH_WARNING
```

See `evaluation.md` section 8a for repair prompt details and per-failure-type retry policy.

## 13. Stage 11: Evaluation

See `evaluation.md`.

## 14. Stage 12: Dashboard

Implemented as a Streamlit app in `dashboard/app.py`. Five pages:

1. **Scan** — trigger a scan from a manifest + catalog, or run the demo scan with one click. Load an existing report JSON.
2. **Adoption Overview** — per-capability metrics: adoption rate, adopted count, custom implementation count, missing count, unknown count, exempt count. Adoption rate denominator excludes NOT_ELIGIBLE and EXEMPT repos.
3. **Repo Matrix** — grid of repo × capability with status icons. All statuses shown with colour coding.
4. **Evidence Drill-Down** — select a repo to see every `EvidenceItem` behind its classification: file path, source type, content summary, and raw code snippet.
5. **LLM Insights** — signal summary, cross-repo insight, prioritised recommendations, validation status, and LLM usage metadata (model, tokens, retries).

Launch:

```bash
uv run streamlit run dashboard/app.py
```

## 15. End-to-End Demo Scenario

Capability: Platform HTTP Client
Demo repos: `demo/repos/` (5 synthetic Python services)
Manifest: `demo/manifest/scan_manifest.yaml`
Catalog: `demo/catalog/catalog.yaml`

```bash
uv run platform-capability scan \
  --manifest demo/manifest/scan_manifest.yaml \
  --catalog demo/catalog/catalog.yaml
```

Detection results:

```text
payment-service          → ADOPTED           (high)   platform-http-client dep + PlatformHttpClient import
reporting-service        → CUSTOM_IMPLEMENTATION (high)  RetrySession class + HTTPAdapter usage
reconciliation-service   → MISSING           (medium)  requests dep only, no retry, no platform wrapper
notification-service     → NOT_ELIGIBLE      (high)   boto3 + jinja2 only, no HTTP client
legacy-analytics-service → CUSTOM_IMPLEMENTATION (medium) requests + httpx, no platform wrapper

Platform HTTP Client:
  Eligible repos  : 4
  Adopted         : 1   (25%)
  Custom impl     : 2
  Missing         : 1
  Not eligible    : 1
```
