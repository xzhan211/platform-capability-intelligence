# Platform Capability Intelligence - Implementation Plan

## 1. Purpose

This document breaks the first demo version into implementation phases and features suitable for PR tracking.

## 2. Team

- 1 tech lead: architecture, catalog loader, detection engine, LLM pipeline, evaluation, demo narrative.
- 1 junior engineer: workspace manager, Python detectors, Streamlit dashboard, demo dataset.
- A third engineer may join once the development process is stable.

## 3. Development Principles

- Catalog-driven from day 1. No detection logic is hardcoded. Every detection rule comes from the capability catalog.
- Detector interfaces are language-agnostic: `Detector.detect(workspace, capability) -> DetectionSignal[]`. Adding Java means adding new detector implementations, not changing the pipeline.
- Deterministic first, LLM second. Classification never requires an LLM. LLM synthesizes already-classified evidence.
- Hard gate checks after every LLM step. Evidence refs, capability IDs, and repo IDs must exist before LLM output is accepted.
- AI-assisted but engineering-controlled. The LLM interprets and narrates; it does not classify or invent.
- EXEMPT status is part of the data model from day 1. UI for managing exceptions is deferred.
- Token budget on CrossRepoEvidenceSummary is enforced before any LLM call.

## 4. Phase 0: Project Foundation

Goal: working skeleton with domain models, config, and CLI stub.

### Feature 0.1: Repository Skeleton

Scope:

- Project folder structure (see architecture.md section 10 for reference layout, adapted for this project).
- README with project description and local run instructions.
- Package setup (`pyproject.toml`).
- Lint and test commands.

```text
PR-001: Initialize project structure and developer tooling
```

Acceptance criteria:

- Project installs locally.
- Test runner works.
- CLI stub accepts `--help`.

### Feature 0.2: Core Domain Models

Scope:

- `Capability` (from catalog: id, name, category, maturity, signal weights, eligibility rules, evidence rules).
- `Tenant` (tenant_id, tenant_name, owner_group).
- `Repository` (repo_id, tenant_id, repo_name, source_type, language_stack).
- `ScanRun` (scan_run_id, scan_batch_id, catalog_version, status, timestamps).
- `DetectionSignal` (signal_id, repo_id, capability_id, signal_type, weight, evidence_ref, confidence).
- `CapabilityDetectionResult` (detection_id, status: ADOPTED|CUSTOM_IMPLEMENTATION|MISSING|NOT_ELIGIBLE|UNKNOWN|EXEMPT, confidence, evidence_refs, unknowns, exempt_reason).
- `EvidenceItem` (evidence_id, repo_id, capability_id, source_type, file_path, line_start, line_end, content_summary).
- `CrossRepoMetric` (metric_id, capability_id, adopted_count, custom_count, missing_count, unknown_count, exempt_count, adoption_rate).
- `CrossRepoEvidenceSummary` (bounded structure passed to LLM; see detection_pipeline.md Stage 10).
- `LLMInsightReport` (structured output from InsightGenerator).
- `EvaluationResult` (hard gate results, soft check scores, final_status).
- `LLMUsageMetadata` (model_id, step, input_tokens, output_tokens, latency_ms).

```text
PR-002: Add core domain models
```

Acceptance criteria:

- All models are serializable to JSON.
- Unit tests exist for serialization and validation.
- `EXEMPT` status is part of `CapabilityDetectionResult`.
- `CrossRepoEvidenceSummary` is a typed model with a `token_count` field.

### Feature 0.3: Configuration System

Scope:

- App config (scan limits, token budget, LLM model ID, prompt versions).
- Storage mode config (local JSON/SQLite vs. future S3/RDS).
- `max_evidence_tokens` default (e.g., 60,000 — smaller than code quality platform because summaries are more compact).

```text
PR-003: Add configuration system
```

Acceptance criteria:

- Config loads from environment or YAML file.
- Defaults documented.
- `max_evidence_tokens` is configurable.

## 5. Phase 1: Capability Catalog and Scan Manifest

Goal: load a versioned YAML capability catalog and parse a multi-repo scan manifest.

### Feature 1.1: Capability Catalog Loader

Scope:

- Parse `capabilities.yaml` into typed `Capability` objects.
- Validate catalog schema: required fields, valid maturity values, signal weight values (high/medium/low).
- Support multiple capabilities in one file; MVP uses one.
- Record `catalog_version` in every scan run.
- Load optional `exceptions.yaml` and merge into capability definitions.

```text
PR-004: Add capability catalog loader and validator
```

Acceptance criteria:

- Valid catalog loads without error.
- Missing required fields raise a clear validation error.
- `catalog_version` is accessible from loaded catalog.
- Exceptions are loaded and merged correctly.
- Unit tests cover valid catalog, missing fields, invalid signal weight, expired exception.

### Feature 1.2: Scan Manifest Parser

Scope:

- Parse `scan_manifest.yaml` into a `ScanBatch` (scan_batch_id, list of repo definitions).
- Each repo definition includes: repo_id, tenant_id, archive path, optional branch and commit_sha.
- Validate that archive paths exist on disk.
- Create `ScanRun` records for each repo.

```text
PR-005: Add scan manifest parser
```

Acceptance criteria:

- Valid manifest loads all repo definitions.
- Missing archive file raises a clear error.
- `ScanBatch` is independent of runtime (no file I/O after parsing).

### Feature 1.3: CLI Entrypoint

Scope:

```bash
platform-capability scan \
  --manifest ./demo-repos/scan_manifest.yaml \
  --catalog ./capabilities/catalog.yaml \
  [--output ./output]
  [--stability-check --runs 3]
```

```text
PR-006: Add CLI entrypoint for scan execution
```

Acceptance criteria:

- CLI accepts manifest, catalog, and output path.
- `--stability-check` flag is accepted (stub implementation).
- Creates scan batch and scan run records.
- Writes basic scan metadata to output folder.

## 6. Phase 2: Workspace Preparation

Goal: unpack each repo archive into a clean, analyzed workspace.

### Feature 2.1: Repo Source Adapter

Scope:

- Define `RepoSourceAdapter` interface: `fetch(repo_definition) -> RepoArtifact`.
- Implement `LocalArchiveSourceAdapter` (zip and tar.gz).
- Return `RepoArtifact` with artifact URI and metadata.

```text
PR-007: Add local repo source adapter
```

Acceptance criteria:

- Zip and tar.gz are both accepted.
- Unsupported format raises a clear error.
- Adapter output is independent of runtime.

### Feature 2.2: Workspace Manager

Scope:

- Unpack archive into isolated temporary workspace.
- Validate size and file count limits.
- Detect languages and frameworks (Python: `requirements.txt`, `setup.py`, `pyproject.toml` present).
- Extract dependency files, config files, and build files into a structured `WorkspaceManifest`.
- Assign stable `file_id` to each file.
- Ignore generated and binary folders (`.git/`, `__pycache__/`, `.venv/`, `build/`, `dist/`).
- Clean up workspace on completion or error.

```text
PR-008: Add workspace manager
```

Acceptance criteria:

- Archive is unpacked to isolated workspace.
- Ignored folders are excluded from inventory.
- `WorkspaceManifest` includes file tree, dependency files, config files.
- Stable file IDs are assigned.
- Workspace is cleaned up after scan.
- Unit tests use small synthetic Python repos.

## 7. Phase 3: Capability Detection

Goal: run catalog-driven detectors and produce weighted detection signals.

### Feature 3.1: Language-Agnostic Detector Interface

Scope:

- Define `Detector` interface: `detect(workspace, capability) -> DetectionSignal[]`.
- Define `DetectionSignal` with signal_type (adoption/reinvention), weight (high/medium/low), evidence_ref, confidence.
- Define `DetectorSuite` runner that runs all registered detectors for a capability and aggregates signals.
- Individual detector failure is captured, not fatal.

```text
PR-009: Add detector interface and suite runner
```

Acceptance criteria:

- Interface contains no language-specific logic.
- Adding a new detector requires only a new class conforming to the interface.
- Suite runner collects signals from all detectors.
- Individual failure produces a warning, not a scan failure.

### Feature 3.2: DependencyDetector (Python)

Scope:

- Scan `requirements.txt`, `setup.py`, `pyproject.toml` for patterns defined in `approved_usage_patterns.dependencies` and `anti_patterns.dependency_patterns`.
- Return signals with weight from catalog.

```text
PR-010: Add Python dependency detector
```

Acceptance criteria:

- Approved dependency produces adoption signal with correct weight.
- Anti-pattern dependency produces reinvention signal with correct weight.
- Handles missing dependency file gracefully.
- Unit tests use small synthetic `requirements.txt` files.

### Feature 3.3: ImportDetector (Python)

Scope:

- Scan Python source files for `import` and `from ... import` statements.
- Match against `approved_usage_patterns.imports` and `anti_patterns.class_name_patterns` (applied to imported names).
- Return signals with catalog-defined weights.

```text
PR-011: Add Python import detector
```

Acceptance criteria:

- Approved import produces adoption signal.
- Anti-pattern import produces reinvention signal.
- Handles syntax errors in Python files gracefully.
- Unit tests use small synthetic Python files.

### Feature 3.4: ConfigDetector (Python)

Scope:

- Scan `.yaml`, `.env`, `.ini`, `.cfg`, `.json` files for config key patterns.
- Match against `approved_usage_patterns.config_keys` and `anti_patterns.code_patterns` (where applicable).
- Return signals with catalog-defined weights.

```text
PR-012: Add config file detector
```

Acceptance criteria:

- Approved config key produces adoption signal.
- Anti-pattern config key produces reinvention signal.
- Unit tests cover YAML, .env, and .ini formats.

### Feature 3.5: CodePatternDetector (Python)

Scope:

- Scan Python source files for class names and function names matching `anti_patterns.class_name_patterns`.
- Use regex patterns from catalog (support wildcards, case-insensitive matching).
- Return reinvention signals with catalog-defined weights and code snippet evidence.

```text
PR-013: Add code pattern detector
```

Acceptance criteria:

- Class name matching anti-pattern produces reinvention signal.
- Code snippet (file path + line range) is attached as evidence item.
- Wildcard patterns work correctly.
- Unit tests cover exact match, wildcard match, no match.

## 8. Phase 4: Classification and Cross-Repo Aggregation

Goal: classify each repo-capability pair deterministically and produce cross-repo metrics and the bounded LLM input structure.

### Feature 4.1: Evidence Selector

Scope:

- Select bounded evidence items per repo-capability pair.
- Priority order: catalog-required files first, then high-weight adoption signals, then high-weight reinvention signals, then medium-weight signals, then representative snippets.
- Enforce token budget (`max_evidence_tokens` from config).
- Assign stable `evidence_id` to every selected item.
- Log token count per selection.

```text
PR-014: Add evidence selector with token budget
```

Acceptance criteria:

- Evidence package never exceeds token budget.
- Every selected item has a stable evidence_id.
- Token count is logged.
- Unit tests: normal case, budget exceeded (truncation), no signals found.

### Feature 4.2: Capability Usage Classifier

Scope:

- Apply signal weight rules from capability catalog to produce a deterministic classification.
- Rules (from catalog section 3 Signal Weight Classification):
  - `ADOPTED`: ≥1 high-weight adoption signal OR ≥2 medium-weight adoption signals.
  - `CUSTOM_IMPLEMENTATION`: (≥1 high-weight reinvention OR ≥2 medium-weight reinvention) AND no high-weight adoption signal.
  - `MISSING`: eligible, no adoption signals, reinvention below threshold.
  - `NOT_ELIGIBLE`: no eligibility rule matched.
  - `UNKNOWN`: insufficient evidence.
  - `EXEMPT`: repo appears in exceptions list with valid, non-expired entry.
- Include confidence level (high/medium/low/unknown) based on signal strength.
- Every classification includes evidence_refs and unknowns.

```text
PR-015: Add deterministic capability usage classifier
```

Acceptance criteria:

- All 6 statuses are reachable and tested.
- Classification is reproducible for the same signals and catalog.
- EXEMPT status excludes the repo from adoption rate denominator.
- Unit tests cover each status and edge cases (expired exception, conflicting signals).

### Feature 4.3: Cross-Repo Aggregator and CrossRepoEvidenceSummary Builder

Scope:

- Aggregate per-repo `CapabilityDetectionResult` into `CrossRepoMetric` (adoption rate, counts).
- Build `CrossRepoEvidenceSummary` (bounded structured input for LLM):
  - aggregate metrics;
  - per-repo status + confidence + top evidence refs (max 2-3 per repo);
  - common reinvention patterns (class/dependency patterns found in multiple repos);
  - unknowns list.
- Apply token budget to CrossRepoEvidenceSummary before returning.

```text
PR-016: Add cross-repo aggregator and CrossRepoEvidenceSummary builder
```

Acceptance criteria:

- Adoption rate excludes EXEMPT and NOT_ELIGIBLE repos from denominator.
- CrossRepoEvidenceSummary is within token budget.
- Common reinvention patterns are extracted from signals across repos.
- Unit tests cover single repo, multiple repos, all-NOT_ELIGIBLE case.

## 9. Phase 5: LLM Insight Pipeline and Evaluation

Goal: generate evidence-grounded platform insights using a validated multi-step LLM pipeline.

### Feature 5.1: LLM Output Schemas

Scope:

- `SignalSummarizerOutput` schema (capability_id, adoption_pattern_summary, reinvention_pattern_summary, evidence_refs, unknowns, confidence).
- `InsightGeneratorOutput` schema (insight_summary, recommendations[], unknowns).
- `Recommendation` schema (recommendation_id, priority, target, action, evidence_refs).

```text
PR-017: Define LLM step schemas and Pydantic validation models
```

Acceptance criteria:

- Schemas support evidence_refs.
- Pydantic models exist for each schema.
- Unit tests validate good and bad examples.

### Feature 5.2: LLM Client Interface and Claude Bedrock Adapter

Scope:

- Define `LLMClient` interface: `call(prompt, tool_definition, tool_choice) -> structured_output`.
- Implement `BedrockLLMClient` with `tool_choice: {"type": "tool"}` for every call (structured output enforced at API level).
- Implement `MockLLMClient` for unit tests.
- Record `LLMUsageMetadata` (model_id, step, input_tokens, output_tokens, latency_ms) per call.

```text
PR-018: Add LLM client interface and Claude Bedrock adapter with structured output
```

Acceptance criteria:

- Core pipeline runs with MockLLMClient without Bedrock access.
- BedrockLLMClient enforces tool use on every call.
- LLMUsageMetadata is populated after every real call.

### Feature 5.3: Prompt and Rubric v1

Scope:

- SignalSummarizer system prompt: LLM must only summarize evidence from CrossRepoEvidenceSummary; must not invent repo IDs, capability IDs, or tenant names.
- InsightGenerator system prompt: cross-repo insight + actionable recommendations; every recommendation must cite evidence_refs.
- Both prompts versioned (v1.0).

```text
PR-019: Add prompt and rubric v1 for SignalSummarizer and InsightGenerator
```

Acceptance criteria:

- Prompts instruct LLM to cite only evidence_refs from the input.
- Prompt and rubric versions are stored in every scan result.
- Tested with MockLLMClient.

### Feature 5.4: SignalSummarizer

Scope:

- Build SignalSummarizer prompt from CrossRepoEvidenceSummary + capability catalog entry.
- Call LLM with `SignalSummarizerOutput` tool definition.
- Store raw output.

```text
PR-020: Implement SignalSummarizer LLM step
```

Acceptance criteria:

- Output conforms to `SignalSummarizerOutput` schema.
- Raw output stored with prompt version and model ID.
- Works with MockLLMClient.

### Feature 5.5: Hard Gate Evaluator

Scope:

- After each LLM step, run deterministic hard gate checks in code (no LLM):
  - all evidence_refs cited exist in the evidence package;
  - all capability_ids cited exist in the catalog;
  - all repo_ids cited exist in the scan batch;
  - no hallucinated names (file paths, class names, tenant names not in input);
  - required schema fields present;
  - output can be serialized without error.
- On failure: trigger targeted repair prompt (grounding repair or schema repair) up to max retry (default: 2).
- On max retry exceeded: fall back to deterministic-only report.

```text
PR-021: Add hard gate evaluator (deterministic)
```

Acceptance criteria:

- Each check is independently testable.
- No LLM is used for hard gate validation.
- Failures produce structured failure reasons.
- Fallback to deterministic report works.

### Feature 5.6: InsightGenerator

Scope:

- Build InsightGenerator prompt from validated SignalSummarizer output + aggregate metrics.
- Call LLM with `InsightGeneratorOutput` tool definition.
- Run hard gate checks after.
- Store raw output.

```text
PR-022: Implement InsightGenerator LLM step
```

Acceptance criteria:

- Recommendations cite evidence_refs.
- Hard gate check runs after InsightGenerator.
- Works with MockLLMClient.

### Feature 5.7: ReportAssembler

Scope:

- Deterministically assemble the final report from validated SignalSummarizer and InsightGenerator outputs.
- Attach catalog version, prompt versions, model IDs, LLM usage metadata.
- Produce `FinalReport` for storage and dashboard.
- No LLM is called.

```text
PR-023: Implement deterministic ReportAssembler
```

Acceptance criteria:

- Output is deterministic given the same validated inputs.
- LLM usage metadata (tokens, latency per step) is included.
- No LLM is called.

## 10. Phase 6: Dashboard

Goal: Streamlit dashboard showing adoption overview, repo-capability matrix, evidence drill-down, and LLM insights with validation status.

### Feature 6.1: FastAPI Scan API

Scope:

- `POST /api/scans` — accepts manifest + catalog, triggers batch scan.
- `GET /api/scans/{scan_batch_id}` — returns scan status.
- `GET /api/scans/{scan_batch_id}/report` — returns final report.

```text
PR-024: Add FastAPI scan API
```

Acceptance criteria:

- Scan can be triggered via API.
- Status can be polled.
- Report can be retrieved.

### Feature 6.2: Background Scan Execution

Scope:

- API triggers scan as a background task.
- Status updated at each pipeline stage.

```text
PR-025: Add background scan execution with stage-level status tracking
```

### Feature 6.3: Streamlit Scan Trigger Page

Scope:

- Upload scan manifest and catalog YAML.
- Trigger scan.
- Show scan status by stage.

```text
PR-026: Add Streamlit scan trigger page
```

### Feature 6.4: Adoption Overview Page

Scope:

Per capability:

- Adoption rate (eligible repos only; EXEMPT excluded from denominator).
- Bar or table: ADOPTED / CUSTOM_IMPLEMENTATION / MISSING / UNKNOWN / EXEMPT counts.
- Confidence distribution.

```text
PR-027: Add adoption overview dashboard page
```

Acceptance criteria:

- EXEMPT repos shown separately, not counted in adoption rate.
- Adoption rate formula is visible (hover or footnote).

### Feature 6.5: Repo-Capability Matrix Page

Scope:

- Grid: rows = repos, columns = capabilities.
- Cells show status icon + confidence.
- Click cell → evidence drill-down.

```text
PR-028: Add repo-capability matrix page
```

### Feature 6.6: Evidence Drill-Down Page

Scope:

- Show all evidence items for a repo-capability pair.
- For each evidence item: source_type, file_path, line range, content_summary.
- For code snippets: show the actual snippet.
- Show classification status and reasoning.

```text
PR-029: Add evidence drill-down page
```

Acceptance criteria:

- Every classification is traceable to its evidence items.
- No "trust me" classifications — everything is backed by visible evidence.

### Feature 6.7: LLM Insight Page

Scope:

- Show SignalSummarizer and InsightGenerator output.
- Show validation status (ACCEPTED / ACCEPTED_WITH_WARNING / FAILED_FALLBACK_TO_DETERMINISTIC).
- Show evidence coverage (percentage of insights backed by evidence_refs).
- Show LLM usage metadata (model, tokens, retries).
- Show recommended platform actions.

```text
PR-030: Add LLM insight and validation status page
```

### Feature 6.8: Demo Story Mode

Scope:

Add a guided story mode for leadership demo. Uses preloaded demo scan (no live LLM required).

Steps:
1. Show capability catalog entry (detection rules, signal weights, eligibility rules).
2. Run cross-repo scan on 5 synthetic Python repos.
3. Show adoption overview: 1 ADOPTED, 1 CUSTOM_IMPLEMENTATION, 1 MISSING, 1 NOT_ELIGIBLE, 1 UNKNOWN.
4. Click into CUSTOM_IMPLEMENTATION repo — show evidence trail (snowflake-connector-python in requirements.txt + SnowflakeTokenManager.py snippet).
5. Show LLM insight: "One repo implements custom Snowflake authentication. Recommend migration guide."
6. Show evaluation status: validation passed, evidence coverage 100%, retry count 0.
7. Show recommended platform actions.

```text
PR-031: Add demo story mode with preloaded scan data
```

Acceptance criteria:

- Story mode runs without a live LLM call (preloaded data).
- Evidence trail is navigable (classification → evidence → source snippet).
- Validation status is visible.
- Demo is understandable to a non-engineer leadership audience.

## 11. Phase 7: Demo Hardening

Goal: synthetic demo repos, golden dataset, Docker, structured logging.

### Feature 7.1: Synthetic Demo Repos (Python)

Scope:

5 synthetic Python repos matching demo_narrative.md:

- `payment-service`: uses `platform-snowflake-auth` → ADOPTED.
- `reporting-service`: uses `snowflake-connector-python` + `SnowflakeTokenManager` class → CUSTOM_IMPLEMENTATION.
- `reconciliation-service`: Snowflake config present, no auth pattern → MISSING.
- `notification-service`: no Snowflake usage → NOT_ELIGIBLE.
- `legacy-analytics-service`: ambiguous Snowflake usage → UNKNOWN.

Each repo is a minimal but realistic Python service (5-15 files).

```text
PR-032: Add 5 synthetic Python demo repos and scan_manifest.yaml
```

Acceptance criteria:

- Scan produces expected classifications for all 5 repos.
- Evidence items are specific and navigable.
- No real company code or credentials.

### Feature 7.2: Golden Dataset

Scope:

- Store expected classifications for all 5 demo repos.
- Regression test: scan demo repos and assert expected statuses match.
- Run regression when detection rules, catalog, or prompts change.

```text
PR-033: Add golden dataset and regression test
```

Acceptance criteria:

- Regression test passes on clean run.
- Test output shows per-repo classification vs. expected.

### Feature 7.3: Structured Logging and Observability

Scope:

- Structured logs per scan stage: scan_batch_id, repo_id, stage, duration, status, error.
- LLM usage logged per step without including raw source code.
- Scan summary logged on completion.

```text
PR-034: Add structured logging and scan stage timing
```

### Feature 7.4: Dockerfile and Docker Compose

Scope:

- Dockerfile for CLI + API runtime.
- Docker Compose: API + Streamlit dashboard + local storage.

```text
PR-035: Add Dockerfile and docker-compose for local demo
```

Acceptance criteria:

- `docker compose up` starts the full demo stack.
- CLI scan works inside container.

## 12. Suggested Timeline (2-Person Team)

### Weeks 1–2: Foundation, Catalog, Workspace

Target:

- Project skeleton, domain models, config.
- Capability catalog loader.
- Scan manifest parser.
- CLI entrypoint.
- Workspace manager (Python repos).

Key PRs: PR-001 to PR-008.

End of week 2 checkpoint: CLI accepts a manifest + catalog, unpacks archives, produces a workspace manifest per repo.

### Weeks 3–4: Detection and Classification

Target:

- All four Python detectors (dependency, import, config, code pattern).
- Evidence selector with token budget.
- Capability usage classifier (all 6 statuses).
- Cross-repo aggregator and CrossRepoEvidenceSummary builder.

Key PRs: PR-009 to PR-016.

End of week 4 checkpoint: CLI produces deterministic classifications for all demo repos without LLM. Output: `classification_results.json`.

### Weeks 5–6: LLM Pipeline and Evaluation

Target:

- LLM schemas, Bedrock adapter, prompts v1.
- SignalSummarizer, hard gate evaluator, InsightGenerator, ReportAssembler.
- Retry/fallback to deterministic report.

Key PRs: PR-017 to PR-023.

End of week 6 checkpoint: Full scan with LLM produces validated insights. Show retry scenario with MockLLMClient.

### Weeks 7–8: Dashboard, Demo Data, Hardening

Target:

- FastAPI endpoints, Streamlit dashboard (all pages).
- Demo story mode.
- 5 synthetic demo repos + golden dataset.
- Docker, logging.

Key PRs: PR-024 to PR-035.

End of week 8 checkpoint: One-command demo. Leadership story mode works. Golden dataset regression passes.

## 13. Definition of Done for Demo

The demo is complete when:

- CLI accepts `scan_manifest.yaml` + `catalog.yaml` and produces results for all repos.
- All 6 classification statuses are reachable and demonstrated.
- EXEMPT repos are excluded from adoption rate denominator.
- Every classification is backed by evidence items with file paths.
- CrossRepoEvidenceSummary is bounded and logged.
- LLM insight pipeline produces validated output.
- Hard gate evaluator catches hallucinated repo/capability IDs.
- Fallback to deterministic report works when LLM fails.
- Dashboard shows adoption overview, repo-capability matrix, evidence drill-down, and LLM insight with validation status.
- Demo story mode runs from preloaded data without a live LLM call.
- 5 synthetic Python repos produce expected classifications (golden dataset passes).
- App runs locally or in Docker.

## 14. PR Review Checklist

Every PR should answer:

- Is the feature small and reviewable?
- Does it preserve the detector interface boundary (no language-specific logic in the interface)?
- Does it preserve the catalog-driven principle (no hardcoded detection rules)?
- Does it add or update tests?
- Does it avoid logging source code or credentials?
- Does it store version metadata where relevant?
- If it touches classification: is the result still deterministic from catalog rules?
- If it touches the LLM pipeline: does the output pass the hard gate evaluator?
- Does it fail safely and produce a diagnosable error?

## 15. Deferred to Phase 2

- Java detection (add `JavaDependencyDetector`, `JavaImportDetector`, `JavaCodePatternDetector` — no pipeline changes).
- Bitbucket source adapter.
- Second capability in catalog.
- Git history / churn × reinvention temporal signal.
- Backstage / developer portal integration.
- Exception/EXEMPT management UI (data model is ready).
- LLM-as-judge soft evaluator.
- Portfolio-scale multi-capability reporting.
- Adoption trend over time.
- Automated migration recommendations.
