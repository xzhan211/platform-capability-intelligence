# Implementation Summary

## Status: v0.1.0 — Demo Complete

This document describes what was actually built, the decisions made during implementation, and what is deferred to Phase 2. It replaces the original phased plan now that the first version is working.

---

## What Was Built

### Project Layout

```
platform-capability-intelligence/
├── src/platform_capability/
│   ├── models.py                       # All Pydantic domain models
│   ├── config.py                       # Settings (PCI_ env vars, .env)
│   ├── cli.py                          # Click CLI (scan, show commands)
│   ├── catalog/
│   │   └── loader.py                   # YAML catalog parser
│   ├── workspace/
│   │   ├── manifest.py                 # scan_manifest.yaml parser
│   │   └── manager.py                  # Archive extraction, file inventory
│   ├── detectors/
│   │   ├── base.py                     # Detector interface
│   │   ├── dependency.py               # requirements.txt, setup.py, pyproject.toml
│   │   ├── import_detector.py          # Python import statements
│   │   ├── code_pattern.py             # Class/function names, inline patterns
│   │   └── namespace.py                # Generic platform prefix matching (Tier 1)
│   ├── classification/
│   │   ├── classifier.py               # Deterministic signal-weight classifier
│   │   └── aggregator.py               # CrossRepoAggregator + CrossRepoEvidenceSummary
│   ├── llm/
│   │   ├── schemas.py                  # Pydantic schemas for LLM outputs
│   │   ├── mock_client.py              # Scripted mock LLM (no credentials needed)
│   │   └── pipeline.py                 # SignalSummarizer → InsightGenerator → ReportAssembler
│   └── pipeline/
│       └── scan_pipeline.py            # End-to-end scan orchestrator
├── dashboard/
│   └── app.py                          # Streamlit dashboard (5 pages)
├── demo/
│   ├── catalog/catalog.yaml            # Platform HTTP Client capability definition
│   ├── manifest/scan_manifest.yaml     # 5 demo repos
│   └── repos/                          # Synthetic Python microservices (zipped)
│       ├── payment-service.zip         # ADOPTED
│       ├── reporting-service.zip       # CUSTOM_IMPLEMENTATION
│       ├── reconciliation-service.zip  # MISSING
│       ├── notification-service.zip    # NOT_ELIGIBLE
│       └── legacy-analytics-service.zip # CUSTOM_IMPLEMENTATION
└── tests/                              # 104 unit tests, 82% coverage
```

---

## Key Implementation Decisions

### Demo Capability: Platform HTTP Client (not Snowflake Auth)

The design docs originally used Snowflake authentication as the demo example. During implementation, **Platform HTTP Client** was chosen instead because:
- HTTP client usage patterns are universal and immediately understandable
- `requests`/`httpx` anti-patterns are simpler to detect than database-auth patterns
- The demo story (retry logic reinvention) is clear to any engineering audience

The catalog schema, detection engine, and dashboard are all capability-agnostic. Switching to any other capability requires only a new YAML entry.

### Python-First Detection

All four detectors parse Python source files. The `Detector` interface (`detectors/base.py`) is language-agnostic — adding Java detection means adding `JavaDependencyDetector`, `JavaImportDetector`, etc. with no changes to the pipeline.

### Mock LLM by Default

The demo runs without AWS credentials. `llm/mock_client.py` produces scripted but realistic `SignalSummarizerOutput` and `InsightGeneratorOutput` based on the actual detection results. Switching to AWS Bedrock requires `PCI_LLM_PROVIDER=bedrock` and valid AWS credentials.

### Hard Gate Evaluation in the Pipeline

The evaluator is integrated directly into `llm/pipeline.py` rather than as a separate stage. After each LLM step, evidence refs, capability IDs, and repo IDs are validated. Invalid refs are stripped; hallucinated targets trigger a warning. On max retry exhaustion, the pipeline falls back to deterministic-only output.

### JSON Files, No Database

All output is plain JSON written to `./output/`. No SQLite or PostgreSQL is required for the local demo. The `FinalReport` model serializes to a single self-contained JSON file per scan batch.

### uv for Package Management

`uv` is used instead of `pip`. `uv.lock` provides deterministic installs. `.python-version` pins Python 3.11.

---

## Running the Demo

```bash
# Install
uv sync

# CLI scan
uv run platform-capability scan \
  --manifest demo/manifest/scan_manifest.yaml \
  --catalog demo/catalog/catalog.yaml

# Dashboard
uv run streamlit run dashboard/app.py

# Tests
uv sync --all-extras
uv run pytest
```

---

## Test Coverage

104 tests across 8 test modules. Current coverage: 82%.

| Module | Coverage |
|---|---|
| models.py | 100% |
| catalog/loader.py | 100% |
| workspace/manifest.py | 100% |
| workspace/manager.py | 100% |
| classification/aggregator.py | 100% |
| llm/mock_client.py | 100% |
| config.py | 100% |
| detectors/import_detector.py | 93% |
| detectors/code_pattern.py | 93% |
| detectors/namespace.py | 89% |
| llm/pipeline.py | 79% |
| classification/classifier.py | 74% |
| detectors/dependency.py | 74% |
| pipeline/scan_pipeline.py | 0% (integration, tested via CLI) |

---

## Phase 2 Backlog

In priority order:

1. **Java detection** — add `JavaDependencyDetector` (pom.xml, build.gradle), `JavaImportDetector`, `JavaCodePatternDetector`; no pipeline changes needed
2. **Second capability in catalog** — e.g., platform logging wrapper or CI/CD template; no code changes needed
3. **SonarQube adapter stub** — ingest SonarQube findings as additional reinvention signals
4. **Bitbucket source adapter** — download archives from Bitbucket instead of requiring local upload
5. **CatalogBootstrapper** — query internal artifact registry to auto-generate `draft` catalog entries
6. **LLM-as-judge soft evaluator** — use a lightweight LLM call to score recommendation actionability and clarity
7. **Developer portal integration** — surface adoption metrics in Backstage or Cortex
8. **Churn × reinvention signal** — combine git churn history with reinvention detection to prioritise highest-risk repos
9. **FastAPI service mode** — background scan execution, scan status polling, API-driven dashboard
10. **AWS production deployment** — Bedrock + S3 + RDS + ECS Fargate
