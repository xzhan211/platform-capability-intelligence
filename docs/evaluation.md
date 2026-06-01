# Evaluation Strategy

## 1. Purpose

Evaluation ensures that capability adoption insights are accurate, evidence-backed, and trustworthy.

The system should not simply let an LLM make unverified claims. The evaluation layer must validate detection results, evidence references, classification outputs, and LLM-generated insights.

## 2. Evaluation Principles

1. **No evidence, no claim**
   - Every adoption, missing, or custom implementation claim must reference evidence.

2. **Catalog-driven validation**
   - Capability IDs and rules must come from the versioned capability catalog.

3. **Deterministic hard gates first**
   - Hard validation should be implemented in code, not by LLM.

4. **LLM is a synthesis layer, not the source of truth**
   - LLM can interpret and summarize, but it cannot invent capabilities, repos, tenants, or usage patterns.

5. **Uncertainty must be explicit**
   - Missing or ambiguous data should be listed as unknowns.

## 3. What Needs to Be Evaluated

### 3.1 Detection Quality

Are deterministic detectors correctly identifying adoption and reinvention signals?

Checks:

- dependency detection accuracy;
- import detection accuracy;
- config detection accuracy;
- template detection accuracy;
- code pattern detection accuracy;
- false positives and false negatives.

### 3.2 Classification Quality

Are repository-capability statuses correct?

Statuses:

- `ADOPTED`
- `CUSTOM_IMPLEMENTATION`
- `MISSING`
- `NOT_ELIGIBLE`
- `UNKNOWN`

Checks:

- status follows catalog rules;
- eligibility was evaluated before adoption rate calculation;
- classification includes evidence refs;
- confidence level matches evidence strength.

### 3.3 LLM Insight Quality

Are LLM-generated summaries and recommendations valid and useful?

Checks:

- all claims are grounded in evidence;
- no unsupported repository/capability names are introduced;
- recommendations are specific and actionable;
- unknowns are included where evidence is incomplete;
- summary does not overstate confidence.

### 3.4 Cross-Repo Metric Quality

Are aggregate metrics computed correctly?

Checks:

- denominator includes only eligible repos when calculating adoption rate;
- `NOT_ELIGIBLE` repos are excluded from adoption denominator;
- `UNKNOWN` is tracked separately;
- metric formula and catalog version are recorded.

## 4. Hard Gate Validation

Hard gates block the final report or require retry/repair.

Hard checks:

- capability ID exists in catalog;
- repo ID exists;
- tenant ID exists or is marked unknown;
- evidence refs exist;
- file paths exist;
- line ranges are valid;
- classification status is a valid enum;
- LLM output schema is valid;
- LLM insight does not mention nonexistent repos, files, tenants, or capabilities.

Possible statuses:

- `ACCEPTED`
- `ACCEPTED_WITH_WARNING`
- `RETRY_REQUIRED`
- `FAILED_FALLBACK_TO_DETERMINISTIC_REPORT`

## 5. Soft Quality Checks

Soft checks do not block the report but affect confidence and report quality score.

Soft checks:

- evidence coverage: percentage of claims backed by evidence;
- recommendation actionability;
- unknowns coverage;
- clarity of cross-repo insight;
- confidence level;
- detection completeness.

Example:

```text
A report may be accepted with warning if all hard gates pass, but only 60% of insights have strong evidence or several repos have unknown tenant metadata.
```

## 6. Capability Detection Confidence

Each detection result should include confidence.

Suggested levels:

- `high`: approved dependency/import/template detected or strong reinvention evidence detected;
- `medium`: multiple weak signals detected;
- `low`: ambiguous signal detected;
- `unknown`: insufficient evidence.

Example:

```text
ADOPTED / high:
- approved platform dependency found in pom.xml
- approved import found in source code

CUSTOM_IMPLEMENTATION / medium:
- Snowflake JDBC found
- custom SnowflakeTokenManager class found
- no approved platform dependency found
```

## 7. Golden Dataset

The project should maintain a small evaluation dataset.

MVP dataset:

1. Repo with approved Snowflake auth usage.
2. Repo with custom Snowflake auth implementation.
3. Repo with Snowflake usage but unclear auth pattern.
4. Repo with no Snowflake usage.
5. Repo with both approved usage and legacy custom code.

Each repo should have expected classification labels.

This allows regression testing when detection rules, prompts, or catalog definitions change.

## 8. LLM Evaluation

LLM output must be validated after generation.

Recommended LLM output requirements:

- structured output;
- evidence refs for every major insight;
- explicit unknowns;
- concise recommendations;
- no claims outside evidence package.

Tool use or structured output reduces formatting failures but does not eliminate the need for semantic validation.

## 8a. Retry and Repair Strategy

### Why Retry Is Needed Here

This platform uses Claude Bedrock tool use (structured output) for every LLM step. Tool use enforces JSON schema at the API level, eliminating most format failures. However, the LLM can still produce semantically invalid output:

- citing a `repo_id` that does not exist in the scan batch;
- citing a `capability_id` not present in the catalog;
- citing an `evidence_ref` that was not in the CrossRepoEvidenceSummary;
- mentioning a tenant name, file path, or class name not in the input;
- generating a recommendation with no supporting evidence.

These semantic failures are caught by the hard gate evaluator and trigger a targeted repair prompt.

### When to Retry vs. Accept vs. Fall Back

```text
RETRY when:
  - Any evidence_ref cited does not exist in the evidence package.
  - Any capability_id cited does not exist in the catalog.
  - Any repo_id cited does not exist in the scan batch.
  - Any hallucinated tenant name, class name, or file path is detected.
  - Required schema fields are missing (rare with tool use).
  - Output is empty or unusably short.

ACCEPT_WITH_WARNING when:
  - All hard gates pass.
  - Evidence coverage is below threshold (some insights lack evidence_refs).
  - Unknowns are not explicitly listed.
  - Recommendation specificity is low.

FALLBACK_TO_DETERMINISTIC_REPORT when:
  - LLM fails all retries.
  - LLM provider is unavailable.
  - All retries produce hallucinated references.

The scan should still complete if the deterministic detection pipeline succeeded.
The deterministic report (classifications, evidence items, cross-repo metrics) is
always produced before the LLM step and is always available as the fallback.
```

### Max Retry Count

```text
max_retry = 2   (configurable)
```

Each retry attempt must store:

- failure reason (which hard gate failed);
- repair prompt type used;
- attempt number;
- raw failed LLM output URI (for debugging and prompt improvement).

### Repair Prompt Strategy

Retry should not resend the same prompt. Use a targeted repair prompt matched to the failure type.

#### Grounding Repair

Use when evidence_refs, capability_ids, or repo_ids cited in LLM output do not exist in the input.

Prompt intent:

```text
Your previous output referenced items that were not in the provided input.
Specifically: {list of invalid references}.

Regenerate your response using ONLY the following:
- Capability IDs from the catalog: {capability_ids}
- Repo IDs from the scan batch: {repo_ids}
- Evidence refs from the CrossRepoEvidenceSummary: {evidence_ref_ids}

Do not mention any repository, tenant, capability, file, or class name
that does not appear in the input above.
```

This is the most common repair needed. The LLM is given the exact valid IDs it is allowed to use.

#### Schema Repair

Use when required fields are missing or field values violate the schema (rare with tool use enforced).

Prompt intent:

```text
Your previous output was missing required fields or had invalid values.
Validation errors: {error list}.

Regenerate using exactly the required schema. Every recommendation must
include recommendation_id, priority, target, action, and evidence_refs.
```

#### Scope Repair

Use when LLM output makes claims outside the scope of the advisory-only product boundary (e.g., "this repo must be blocked" or "this is a compliance violation").

Prompt intent:

```text
Your previous output made claims outside the advisory scope of this platform.
This platform provides observations and recommendations only. It does not
enforce policy, block releases, or make compliance determinations.

Rewrite your response using advisory language only:
- Use "appears to implement" rather than "violates".
- Use "recommend reviewing" rather than "must be changed".
- Do not reference compliance, policy enforcement, or release gates.
```

### Retry Is Only for LLM Steps

The retry mechanism applies only to the LLM pipeline steps:

- `SignalSummarizer`
- `InsightGenerator`

The deterministic detection steps (DependencyDetector, ImportDetector, ConfigDetector, CodePatternDetector, CapabilityUsageClassifier, CrossRepoAggregator) do not use retry. If a deterministic step fails, it is a bug or a configuration error — not a probabilistic output issue.

## 9. Stability Evaluation

Stability evaluation is optional and not part of the normal scan path.

It can be used for prompt and model validation:

```text
platform-capability scan --input demo-repos --stability-check --runs 3
```

Checks:

- same evidence should produce similar insights;
- top capability gaps should overlap;
- recommendations should be similar;
- confidence should not fluctuate significantly.

Do not enable by default because it increases cost and latency.

## 10. Usage and Cost Metadata

Every LLM call should record usage metadata.

```text
llm_usage_metadata
- scan_run_id
- llm_step
- model_id
- input_tokens
- output_tokens
- retry_count
- latency_ms
- estimated_cost_when_available
```

Cost should be measured from usage data, not guessed in the design.

## 11. MVP Evaluation Requirements

MVP must include:

- deterministic evidence ref validation;
- classification status validation;
- catalog ID validation;
- LLM schema validation;
- report final status;
- at least one golden dataset scenario;
- dashboard display of validation status and confidence.

MVP may defer:

- LLM-as-judge;
- full qualitative scoring;
- complex similarity metrics;
- production-scale benchmarking.
