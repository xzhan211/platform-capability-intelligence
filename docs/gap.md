# Gap Analysis & Todo List

Project-level backlog. Check off items as they are completed.

---

## Catalog & Detection

- [ ] **Second capability in catalog** — add a second platform capability (e.g. platform logging wrapper or CI/CD template) to prove the multi-capability path end-to-end; no code changes needed, only a new `pyproject.toml` + repo entry
- [ ] **Java detection** — add `JavaDependencyDetector` (pom.xml, build.gradle), `JavaImportDetector`, `JavaCodePatternDetector`; the `Detector` interface and pipeline require no changes
- [ ] **CatalogBootstrapper** — query an internal artifact registry (e.g. Artifactory, Nexus) to auto-generate `draft` catalog entries for newly published platform packages
- [ ] **SonarQube adapter** — ingest SonarQube findings as additional reinvention signals alongside the existing detectors

---

## Data Sources

- [ ] **Bitbucket source adapter** — download repo archives from Bitbucket API instead of requiring local zip upload; `WorkspaceManager.prepare()` should accept a URL resolver strategy
- [ ] **Git churn signal** — combine git churn history with reinvention detection to surface highest-risk repos (frequently modified custom implementations = highest migration priority)

---

## LLM & Evaluation

- [ ] **Real LLM end-to-end test** — run a full scan with `PCI_LLM_PROVIDER=bedrock` against the demo repos and validate that the hard-gate evaluator passes; currently only the mock path is exercised
- [ ] **LLM-as-judge soft evaluator** — use a lightweight LLM call to score recommendation actionability and clarity, supplementing the deterministic hard-gate check

---

## Infrastructure & Deployment

- [ ] **FastAPI service mode** — expose scan as a background job via REST API; add scan status polling and webhook-on-complete; dashboard calls the API instead of spawning a subprocess
- [ ] **AWS production deployment** — Bedrock for LLM, S3 for report storage, RDS for scan history, ECS Fargate for the API service

---

## Integrations

- [ ] **Developer portal integration** — surface adoption metrics in Backstage or Cortex as a plugin; platform engineers should not need to open the standalone dashboard

---

## Demo & Docs

- ✅ **Platform repo extraction** — catalog derived directly from platform repo source (`platform_manifest.yaml`) instead of hand-authored `catalog.yaml`; eligibility rules and anti-patterns declared in `[tool.platform]` of the platform repo's `pyproject.toml`
- [ ] **Multi-repo demo** — add a second platform capability to the demo so the Repo Matrix page shows a meaningful N×M grid rather than N×1
- [ ] **Demo script / recorded walkthrough** — a short screen recording or step-by-step narrative for async stakeholder review
