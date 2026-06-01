# Demo Narrative

## 1. Demo Goal

The demo should show that the application can identify whether platform capabilities are being adopted across tenant repositories and where teams are reinventing capabilities that the platform already provides.

The demo should not focus on generic code quality. It should focus on platform value:

> Are our reusable building blocks actually being used, and where do tenants still rebuild things themselves?

## 2. Recommended Demo Story

Use Snowflake authentication as the primary example.

Story:

1. The platform provides a reusable Snowflake authentication capability.
2. Several tenant repositories need Snowflake access.
3. Some use the platform capability correctly.
4. Some implement custom authentication/token handling.
5. One repo has ambiguous Snowflake usage and needs follow-up.
6. The dashboard shows adoption rate, custom implementation signals, and evidence.
7. The final recommendation is to improve onboarding material, provide migration templates, and reach out to tenants with custom implementations.

## 3. Demo Dataset

Use 4-5 synthetic repositories.

### Repo A: payment-service

Expected status:

```text
ADOPTED
```

Evidence:

- approved platform Snowflake auth dependency;
- approved import;
- platform config key.

### Repo B: reporting-service

Expected status:

```text
CUSTOM_IMPLEMENTATION
```

Evidence:

- Snowflake JDBC dependency;
- no platform auth dependency;
- custom `SnowflakeTokenManager` class;
- token refresh logic.

### Repo C: reconciliation-service

Expected status:

```text
MISSING
```

Evidence:

- Snowflake config exists;
- no approved platform dependency;
- no strong custom implementation detected.

### Repo D: notification-service

Expected status:

```text
NOT_ELIGIBLE
```

Evidence:

- no Snowflake dependency;
- no Snowflake config;
- no Snowflake source files.

### Repo E: legacy-analytics-service

Expected status:

```text
UNKNOWN or CUSTOM_IMPLEMENTATION depending on signal strength
```

Evidence:

- some Snowflake config;
- legacy helper class;
- insufficient evidence to classify with high confidence.

## 4. Demo Flow

### Step 1: Introduce the Platform Problem

Message:

```text
We already have tools for repo-level quality. The missing view is cross-repo platform capability adoption. We need to know whether shared platform building blocks are actually being reused across tenants.
```

### Step 2: Show Capability Catalog

Show Snowflake Auth capability definition:

- approved dependency;
- approved import;
- config key;
- anti-patterns;
- eligibility rules.

Message:

```text
The system is catalog-driven. It cannot claim adoption unless the capability and detection rules are explicitly defined.
```

### Step 3: Run Cross-Repo Scan

Run:

```text
platform-capability scan --input ./demo-repos --catalog ./capabilities.yaml
```

Message:

```text
The scan analyzes multiple tenant repositories and classifies each repo-capability pair.
```

### Step 4: Show Adoption Overview

Example dashboard:

```text
Snowflake Authentication
Eligible repos: 4
Adopted: 1
Custom implementation: 1
Missing: 1
Unknown: 1
Not eligible: 1
```

Message:

```text
This gives platform leadership a direct view of whether a shared capability is actually being reused.
```

### Step 5: Show Evidence Trail

Click into `reporting-service`.

Show:

- `pom.xml`: Snowflake JDBC dependency;
- missing platform auth dependency;
- `SnowflakeTokenManager.java`;
- code snippet around token refresh logic.

Message:

```text
The custom implementation classification is not an LLM guess. It is backed by concrete evidence.
```

### Step 6: Show LLM Insight

Example insight:

```text
The strongest platform adoption gap is Snowflake authentication. Among eligible repositories, several do not use the approved platform capability. One repository appears to implement custom token refresh logic. This suggests that onboarding documentation or migration examples for batch-style Snowflake integration may be insufficient.
```

Message:

```text
The LLM is used to synthesize evidence into platform-level insight, not to invent unsupported claims.
```

### Step 7: Show Evaluation Status

Dashboard should show:

```text
Validation Status: ACCEPTED
Evidence Coverage: High
Unknowns Listed: Yes
LLM Claims Validated: Passed
```

Message:

```text
The report is validated before display. If the LLM mentions unsupported repos or capabilities, the report is rejected or falls back to deterministic output.
```

### Step 8: Show Recommended Platform Actions

Example recommendations:

1. Publish a migration guide for teams using direct Snowflake JDBC.
2. Add a batch-job example to the Snowflake Auth documentation.
3. Reach out to reporting-service owner to migrate custom token refresh logic.
4. Add catalog rules for additional Snowflake usage patterns discovered during scan.

Message:

```text
The output is actionable for platform teams. It helps decide which capabilities need better onboarding, migration support, or outreach.
```

## 5. Demo Aha Moment

The key aha moment is:

```text
This tool does not just inspect whether one repo has good or bad code.
It tells us whether the platform's reusable capabilities are actually being adopted across tenants, where teams are rebuilding platform-provided integrations, and what we should improve to make onboarding easier.
```

## 6. Leadership Positioning

Use this positioning:

```text
We are not building another code quality scanner.
We are building a cross-repo platform capability intelligence layer that helps us measure adoption, detect reinvention, and improve reusable platform building blocks.
```

## 7. Demo Success Criteria

The demo is successful if the audience understands:

- what capabilities the platform provides;
- which repos/tenants use those capabilities;
- where custom reinvention is happening;
- what evidence supports each classification;
- what platform actions should be taken next;
- why this creates better onboarding and stronger platform stickiness.
