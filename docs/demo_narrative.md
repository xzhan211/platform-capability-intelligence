# Demo Narrative

## 1. Demo Goal

Show that the application can identify whether platform capabilities are being adopted across tenant repositories and where teams are reinventing capabilities that the platform already provides.

The demo does not focus on generic code quality. It focuses on platform value:

> Are our reusable building blocks actually being used, and where do tenants still rebuild things themselves?

## 2. Demo Capability: Platform HTTP Client

The demo uses the **Platform HTTP Client** (`platform-http-client`) as the example capability.

The platform provides a standard HTTP client with built-in retry, circuit breaker, and observability. Teams that use it get reliable HTTP calls for free. Teams that don't end up writing their own retry logic — usually inconsistently, often with bugs.

Capability ID: `platform_http_client`
Catalog: `demo/catalog/catalog.yaml`

## 3. Demo Dataset

Five synthetic Python microservices. Each illustrates a different detection outcome.

### Repo 1: payment-service

**Tenant:** payments-team
**Expected status:** `ADOPTED` (high confidence)

Evidence:
- `requirements.txt` contains `platform-http-client==2.1.0`
- `src/payment_service/clients/payment_gateway.py` imports `from platform_http_client import PlatformHttpClient, HttpClientConfig`
- Uses `PlatformHttpClient` to call the payment gateway

### Repo 2: reporting-service

**Tenant:** analytics-team
**Expected status:** `CUSTOM_IMPLEMENTATION` (high confidence)

Evidence:
- `requirements.txt` contains `requests==2.31.0` (raw library, no platform wrapper)
- `src/reporting_service/http/custom_session.py` defines `class RetrySession(requests.Session):`
- Custom retry logic using `HTTPAdapter` and `urllib3.util.retry.Retry`

### Repo 3: reconciliation-service

**Tenant:** finance-team
**Expected status:** `MISSING` (medium confidence)

Evidence:
- `requirements.txt` contains `requests==2.31.0` (makes it eligible)
- `src/reconciliation_service/fetcher.py` uses plain `requests.get()` with no retry, no platform wrapper
- No custom retry class — just unprotected HTTP calls

### Repo 4: notification-service

**Tenant:** comms-team
**Expected status:** `NOT_ELIGIBLE` (high confidence)

Evidence:
- `requirements.txt` contains only `boto3`, `jinja2`, `pydantic`
- Sends email via AWS SES SDK — no HTTP client needed
- No eligibility signals detected

### Repo 5: legacy-analytics-service

**Tenant:** data-team
**Expected status:** `CUSTOM_IMPLEMENTATION` (medium confidence)

Evidence:
- `requirements.txt` contains both `requests==2.28.0` and `httpx==0.24.1`
- `src/analytics/data_pull.py` uses both libraries inconsistently across sync and async paths
- No platform wrapper, no unified retry strategy

## 4. How to Run the Demo

### CLI

```bash
uv run platform-capability scan \
  --manifest demo/manifest/scan_manifest.yaml \
  --catalog demo/catalog/catalog.yaml \
  --output ./output
```

### Dashboard

```bash
uv run streamlit run dashboard/app.py
```

Open `http://localhost:8501`, go to **Scan**, click **Run Demo Scan**.

## 5. Demo Flow (for Leadership Presentation)

### Step 1: Introduce the Platform Problem

> We already have tools for repo-level code quality. The missing view is cross-repo platform capability adoption. We need to know whether shared platform building blocks are actually being reused across tenants.

### Step 2: Show the Capability Catalog

Open `demo/catalog/catalog.yaml` or the Scan page. Show the Platform HTTP Client capability definition:

- Approved dependency: `platform-http-client` (weight: high)
- Approved import: `platform_http_client.PlatformHttpClient` (weight: high)
- Anti-pattern: `RetrySession` class (weight: high)
- Anti-pattern: `HTTPAdapter` usage (weight: high)
- Eligibility: any repo with `requests`, `httpx`, or `platform-http-client`

> The system is catalog-driven. It cannot claim adoption unless the capability and detection rules are explicitly defined. Detection rules have weights — one high-weight signal is enough to classify.

### Step 3: Run the Scan

```bash
uv run platform-capability scan \
  --manifest demo/manifest/scan_manifest.yaml \
  --catalog demo/catalog/catalog.yaml
```

> The scan analyzes five tenant repositories and classifies each one against the catalog rules.

### Step 4: Show the Adoption Overview

Navigate to **Adoption Overview** in the dashboard:

```
Platform HTTP Client
Eligible repos : 4
Adopted        : 1   (25% adoption rate)
Custom impl    : 2
Missing        : 1
Not eligible   : 1
```

> This gives platform leadership a direct view of whether a shared capability is actually being reused.

### Step 5: Show the Evidence Trail

Navigate to **Evidence Drill-Down**. Select `reporting-service`.

Show:
- `requirements.txt`: `requests==2.31.0` detected (reinvention signal, medium)
- `src/reporting_service/http/custom_session.py`: `class RetrySession(requests.Session)` detected (reinvention signal, high)
- Code snippet showing `HTTPAdapter` and `Retry(...)` usage

> The custom implementation classification is not an LLM guess. It is backed by concrete evidence: a specific file, a specific class name, a specific code pattern.

### Step 6: Show the Repo Matrix

Navigate to **Repo Matrix**.

Show the grid with status icons for each repo × capability combination.

### Step 7: Show LLM Insights

Navigate to **LLM Insights**.

Example insight:
```
The Platform HTTP Client capability has a 25% adoption rate among 4 eligible
repos. 2 repos implement custom alternatives (reporting-service,
legacy-analytics-service). The most common reinvention pattern is direct use
of requests without the platform wrapper. 1 eligible repo is missing the
capability entirely. Platform team should prioritize outreach to repos with
custom implementations.
```

Recommendations shown:
- [HIGH] reporting-service: Migrate RetrySession to platform-http-client
- [HIGH] legacy-analytics-service: Migrate inconsistent HTTP usage to platform-http-client
- [MEDIUM] reconciliation-service: Onboard to platform-http-client
- [MEDIUM] platform-team: Add migration guide for teams using raw requests

Show the **Validation Status** (ACCEPTED) and evidence coverage — proving the LLM output was validated before display.

> The LLM synthesizes evidence into platform-level insight, not to invent unsupported claims. Every recommendation traces back to a specific evidence item.

### Step 8: Show Recommended Platform Actions

The output is actionable for platform teams:

1. Reach out to `reporting-service` owner to migrate `RetrySession` to `platform-http-client`.
2. Reach out to `legacy-analytics-service` owner to consolidate HTTP usage.
3. Add a migration guide for teams currently using raw `requests`.
4. Onboard `reconciliation-service` to the platform capability.

## 6. Demo Aha Moment

```
This tool does not just inspect whether one repo has good or bad code.
It tells us whether the platform's reusable capabilities are actually being
adopted across tenants, where teams are rebuilding platform-provided
integrations, and what we should do to make onboarding easier.
```

## 7. Leadership Positioning

```
We are not building another code quality scanner.
We are building a cross-repo platform capability intelligence layer that
helps us measure adoption, detect reinvention, and improve reusable
platform building blocks.
```

## 8. Demo Success Criteria

The demo is successful if the audience understands:

- what capabilities the platform provides and how they are detected;
- which repos use those capabilities and which do not;
- where custom reinvention is happening and what the evidence is;
- what platform actions should be taken next;
- that this is not a black-box AI tool — every claim is backed by evidence.
