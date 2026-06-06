# Platform Capability Intelligence

Cross-repo intelligence for platform teams. Answers one question:

> Are our reusable platform capabilities actually being used across tenant repositories, or are teams building their own versions?

---

## What It Does

Platform teams invest in shared building blocks — HTTP clients, auth wrappers, logging libraries, CI/CD templates — so tenant teams don't have to rebuild them. But without visibility, there is no way to know whether these capabilities are adopted, ignored, or quietly reimplemented.

This tool scans multiple tenant repositories and classifies each one against a versioned capability catalog:

| Status | Meaning |
|---|---|
| **ADOPTED** | Repo uses the approved platform capability |
| **CUSTOM_IMPLEMENTATION** | Repo appears to have built its own version |
| **MISSING** | Repo needs the capability but hasn't adopted it |
| **NOT_ELIGIBLE** | Capability doesn't apply to this repo |
| **UNKNOWN** | Insufficient evidence to classify |
| **EXEMPT** | Approved exception on record |

After detection, an LLM synthesizes cross-repo insights and produces actionable recommendations for the platform team.

---

## Project Structure

```
platform-capability-intelligence/
├── src/platform_capability/    # Core library
│   ├── catalog/                # Capability catalog loader + platform repo extractor
│   ├── workspace/              # Archive extraction, manifest parsing
│   ├── detectors/              # Dependency, import, code pattern, namespace detectors
│   ├── classification/         # Classifier, cross-repo aggregator
│   ├── llm/                    # LLM pipeline (mock + Bedrock)
│   └── pipeline/               # End-to-end scan orchestrator
├── dashboard/app.py            # Streamlit dashboard
├── demo/
│   ├── catalog/catalog.yaml    # Static capability catalog (hand-authored)
│   ├── manifest/
│   │   ├── scan_manifest.yaml      # Consumer repos to scan
│   │   └── platform_manifest.yaml  # Platform repos to extract catalog from
│   └── repos/
│       ├── platform-http-client/   # Platform library source (catalog source)
│       └── <5 consumer services>   # Synthetic tenant microservices
├── tests/                      # Unit tests (83% coverage)
└── docs/                       # Architecture and design docs
```

---

## Quick Start

### 1. Install

Requires Python 3.11+. Uses [uv](https://docs.astral.sh/uv/) for environment and dependency management.

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone and install
git clone <repo-url>
cd platform-capability-intelligence
uv sync
```

`uv sync` creates a `.venv`, resolves dependencies from `uv.lock`, and installs the package — no manual `pip install` or `venv activate` needed.

### 2. Run the demo scan (CLI)

```bash
uv run platform-capability scan \
  --manifest demo/manifest/scan_manifest.yaml \
  --catalog demo/manifest/platform_manifest.yaml \
  --output ./output
```

Expected output:

```
Platform Capability Intelligence
Manifest : demo/manifest/scan_manifest.yaml
Catalog  : demo/manifest/platform_manifest.yaml
Output   : ./output

Running scan...
  Preparing workspace: payment-service
  Preparing workspace: reporting-service
  Preparing workspace: reconciliation-service
  Preparing workspace: notification-service
  Preparing workspace: legacy-analytics-service

✓ Scan complete (0.1s)

                Detection Results
┌──────────────────────────┬───────────────────┬────────────────────────┐
│ Repo                     │ Status            │ Confidence             │
├──────────────────────────┼───────────────────┼────────────────────────┤
│ payment-service          │ ADOPTED           │ high                   │
│ reporting-service        │ CUSTOM_IMPL       │ high                   │
│ reconciliation-service   │ MISSING           │ medium                 │
│ notification-service     │ NOT_ELIGIBLE      │ high                   │
│ legacy-analytics-service │ CUSTOM_IMPL       │ medium                 │
└──────────────────────────┴───────────────────┴────────────────────────┘

Adoption rate: 25% (1 of 4 eligible repos)
```

### 3. Launch the dashboard

```bash
uv run streamlit run dashboard/app.py
```

Open `http://localhost:8501` in your browser.

---

## Demo Walkthrough

The demo uses a fictional **Platform HTTP Client** capability (`platform-http-client`) — a platform-provided HTTP client with built-in retry, circuit breaker, and observability. Five synthetic Python microservices illustrate every detection outcome.

### The 5 Demo Repos

| Repo | What it does | Expected status |
|---|---|---|
| `payment-service` | Uses `platform-http-client` correctly | ADOPTED |
| `reporting-service` | Custom `RetrySession(requests.Session)` with `HTTPAdapter` | CUSTOM_IMPLEMENTATION |
| `reconciliation-service` | Plain `requests.get()` with no retry or platform wrapper | MISSING |
| `notification-service` | Uses only `boto3` + Jinja2, no HTTP client needed | NOT_ELIGIBLE |
| `legacy-analytics-service` | Uses both `requests` and `httpx` inconsistently | CUSTOM_IMPLEMENTATION |

### Dashboard Pages

**Scan**
Upload a manifest + catalog and trigger a scan, or click **Run Demo Scan** to run instantly against the 5 demo repos.

**Adoption Overview**
Top-level metrics per capability: adoption rate, adopted count, custom implementation count, missing count. The adoption rate denominator excludes NOT_ELIGIBLE and EXEMPT repos.

**Repo Matrix**
A grid showing every repo × capability combination with status icons. Click any cell to jump to the evidence.

**Evidence Drill-Down**
Select a repo to see every piece of evidence behind its classification — dependency file matches, import detections, code pattern matches, and source snippets. Nothing is hidden: every classification traces back to a specific file and line.

**LLM Insights**
The LLM synthesis layer reads the cross-repo evidence summary and produces:
- A plain-English summary of adoption patterns and reinvention patterns
- Prioritized action items for the platform team (HIGH: migrate custom impl, MEDIUM: improve onboarding docs)
- Validation status showing whether LLM output passed evidence reference checks

---

## How the Detection Works

Detection is catalog-driven and primarily deterministic. The LLM only synthesizes — it does not classify.

```
Capability Catalog (YAML)
    ↓
For each repo in the scan manifest:
    Workspace preparation (unzip, file inventory)
    ↓
    Four detectors run in parallel:
        DependencyDetector   → requirements.txt, setup.py, pyproject.toml
        ImportDetector       → Python import statements
        CodePatternDetector  → class/function names matching anti-patterns
        NamespaceDetector    → generic platform prefix matching (Tier 1)
    ↓
    CapabilityUsageClassifier
        (deterministic rules using signal weights from catalog)
    ↓
CrossRepoAggregator → metrics + bounded evidence summary
    ↓
LLM Pipeline (mock by default, Bedrock optional):
    SignalSummarizer → per-capability narrative
    InsightGenerator → cross-repo recommendations
    ReportAssembler  → deterministic final report assembly
    ↓
Hard gate evaluator validates all LLM evidence refs before accepting output
```

### Capability Catalog Format

A capability entry defines what counts as adoption and what counts as reinvention:

```yaml
capability_id: platform_http_client
name: Platform HTTP Client
status: stable

approved_usage_patterns:
  dependencies:
    - pattern: "platform-http-client"
      weight: high        # one high-weight signal → ADOPTED
  imports:
    - pattern: "platform_http_client.PlatformHttpClient"
      weight: high

anti_patterns:
  class_name_patterns:
    - pattern: "RetrySession"
      weight: high        # one high-weight signal → CUSTOM_IMPLEMENTATION
  code_patterns:
    - pattern: "HTTPAdapter"
      weight: high
      note: "manual retry configuration"

eligibility_rules:
  include_if_dependency:
    - "requests"
    - "httpx"
    - "platform-http-client"
```

Signal weights drive classification deterministically:
- **ADOPTED**: ≥1 high-weight adoption signal, or ≥2 medium
- **CUSTOM_IMPLEMENTATION**: ≥1 high-weight reinvention signal, or ≥2 medium (with no high adoption)
- **MISSING**: eligible, no adoption, reinvention below threshold
- **NOT_ELIGIBLE**: no eligibility rule matched

---

## Catalog Sources

The `--catalog` flag accepts two formats, auto-detected by file content.

### Option A: Static YAML (default)

```bash
uv run platform-capability scan \
  --manifest demo/manifest/scan_manifest.yaml \
  --catalog demo/catalog/catalog.yaml
```

You write detection rules (approved patterns, anti-patterns, eligibility rules) by hand in `catalog.yaml`. Required for anti-patterns, which cannot be inferred from code.

### Option B: Extract from Platform Repos

```bash
uv run platform-capability scan \
  --manifest demo/manifest/scan_manifest.yaml \
  --catalog demo/manifest/platform_manifest.yaml
```

Point `--catalog` at a `platform_manifest.yaml` instead. The tool scans each platform repo's source code and automatically derives:

| Extracted from | Produces |
|---|---|
| `pyproject.toml [project].name` | `capability_id`, dependency pattern (high weight) |
| `pyproject.toml [project].description` | `description` |
| `__init__.py __all__` | per-export import patterns (high weight) |
| module name | module-level import pattern (medium weight) |
| `[tool.platform.eligibility_rules]` | eligibility rules (falls back to package name only if absent) |
| `[tool.platform.anti_patterns]` | reinvention signals (empty if absent) |
| `[tool.platform]` other fields | `owner_team`, `documentation_url`, `recommended_for` |
| per-repo metadata in manifest | `category`, `status`, `owner_team` |

Eligibility rules and anti-patterns are declared in the platform repo's own `pyproject.toml` — the platform team knows what counts as reinvention:

```toml
[tool.platform.eligibility_rules]
include_if_dependency = ["requests", "httpx", "platform-http-client"]
include_if_import_prefix = ["requests", "httpx", "platform_http_client"]

[[tool.platform.anti_patterns.class_name_patterns]]
pattern = "RetrySession"
weight = "high"
note = "Custom retry session wrapping requests.Session"

[[tool.platform.anti_patterns.code_patterns]]
pattern = "HTTPAdapter"
weight = "high"
note = "Custom HTTPAdapter — manual retry configuration"
```

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

## Adding Your Own Capability

**With static catalog:**
1. Add an entry to `demo/catalog/catalog.yaml`
2. Define `approved_usage_patterns`, `anti_patterns`, and `eligibility_rules`
3. Add your repos to `demo/manifest/scan_manifest.yaml`
4. Run the scan

**With platform repo extraction:**
1. Ensure your platform library has a `pyproject.toml` with `[project].name` and `[project].description`
2. Ensure `src/<module>/__init__.py` has `__all__` listing public exports
3. Declare `[tool.platform.eligibility_rules]` and `[tool.platform.anti_patterns]` in `pyproject.toml`
4. Add the repo to `demo/manifest/platform_manifest.yaml`
5. Run the scan with `--catalog demo/manifest/platform_manifest.yaml`

No code changes needed in either case.

---

## Running Tests

```bash
uv sync --all-extras   # installs dev dependencies (pytest, ruff, etc.)
uv run pytest
```

Target: 80% coverage. Current: 82%.

---

## Using Real LLM (AWS Bedrock)

By default, the system uses a mock LLM that produces scripted but realistic output — no AWS credentials needed.

To switch to Claude on AWS Bedrock:

```bash
export PCI_LLM_PROVIDER=bedrock
export PCI_LLM_MODEL_ID=anthropic.claude-3-5-sonnet-20241022-v2:0
export AWS_PROFILE=your-profile
uv run platform-capability scan --manifest ... --catalog ...
```

Requires AWS credentials with Bedrock access in your target region.

---

## Configuration

Key environment variables (all prefixed `PCI_`):

| Variable | Default | Description |
|---|---|---|
| `PCI_LLM_PROVIDER` | `mock` | `mock` or `bedrock` |
| `PCI_LLM_MODEL_ID` | Claude 3.5 Sonnet | Bedrock model ID |
| `PCI_LLM_MAX_RETRY` | `2` | Max LLM retry attempts on validation failure |
| `PCI_MAX_EVIDENCE_TOKENS` | `60000` | Token budget for evidence package |
| `PCI_OUTPUT_DIR` | `./output` | Where scan reports are written |

Settings can also be placed in a `.env` file in the project root.
