# Market Research Report: Platform Capability Intelligence

## 1. Executive Summary

This project is not a traditional code quality scanner, static analysis platform, developer portal, or engineering productivity dashboard. The closest framing is:

> **Platform Capability Intelligence**: an internal intelligence layer that measures whether shared platform capabilities are adopted, reused, reinvented, or missing across repositories, tenants, and teams.

The market contains several adjacent product categories:

1. **Internal Developer Portals / Service Catalogs**: Backstage, Cortex, OpsLevel, Port, Roadie, Atlassian Compass, Datadog IDP.
2. **Application Portfolio / Architecture Intelligence**: CAST Highlight, CAST Imaging.
3. **Behavioral Code Analysis / Code Health**: CodeScene.
4. **Developer Productivity / Platform Metrics**: DX, LinearB, Swarmia, Jellyfish, DORA / SPACE-style metrics platforms.
5. **Policy / Governance / Compliance Tools**: OPA, Conftest, Checkov, Snyk IaC, Prisma Cloud, Wiz.
6. **Automated Migration / Refactoring Platforms**: Moderne / OpenRewrite.
7. **AI Engineering Tools**: Diffblue Cover and AI-assisted development quality tools.

None of these categories directly solves the specific internal gap: **cross-repo visibility into whether company-provided platform building blocks are actually reused by tenants, or whether tenant teams are rebuilding the same integrations themselves.**

The proposed product should therefore be positioned as an **internal complement** to existing tools, not a replacement.

---

## 2. Problem Context

Platform teams invest in reusable capabilities such as:

- Snowflake integration and authentication
- standard auth patterns
- logging / observability wrappers
- CI/CD templates
- data access wrappers
- permissioning libraries
- deployment templates
- retry clients
- secrets management helpers
- standard API gateway integration

The business goal is not only to provide these components, but to ensure they are:

1. **adopted broadly** across tenants;
2. **easy to onboard** for new teams;
3. **cheaper to use than reinvent**;
4. **sticky enough** that leaving the platform requires rebuilding a growing set of useful capabilities;
5. **measurable** through cross-repo evidence rather than anecdotal feedback.

Current tools can track code quality or service metadata within individual repositories or services, but they usually do not answer questions such as:

- Which platform capabilities are actually used across tenant repos?
- Which tenants are implementing custom versions of capabilities that the platform already provides?
- Which capabilities are broadly adopted, and which are underused?
- Where is onboarding friction causing teams to reinvent core integrations?
- What reusable capabilities make our platform easier to adopt and harder to leave?

---

## 3. Market Landscape

### 3.1 Internal Developer Portals and Service Catalogs

Representative products:

- Backstage
- Cortex
- OpsLevel
- Port
- Roadie
- Atlassian Compass
- Datadog Internal Developer Portal

#### What they do well

These tools provide a system of record for software components, services, teams, ownership, metadata, documentation, scorecards, standards, and self-service workflows.

Backstage is an open-source framework for building developer portals and is centered around a software catalog that tracks ownership and metadata for services, websites, libraries, data pipelines, and other software entities. Cortex, OpsLevel, Port, Compass, and Datadog IDP provide similar catalog and scorecard concepts, allowing organizations to define standards and measure service maturity, production readiness, security, reliability, and operational hygiene.

#### Relevance to this project

These products are highly relevant because they establish the category of internal developer portals and service catalogs. They are natural places where platform capability adoption metrics could eventually be surfaced.

#### Gaps relative to Platform Capability Intelligence

Most developer portals do not automatically inspect repository code, dependencies, config files, and templates to determine whether a company-specific platform capability is actually adopted or reinvented.

They can answer:

> What services exist? Who owns them? Do they meet defined scorecard criteria?

They typically do not answer:

> Is this tenant using our approved Snowflake Auth capability, or did they implement their own Snowflake authentication layer?

#### Product implication

The proposed app could integrate with or feed data into an internal developer portal later, but the core value is a **capability detection and evidence engine**, not another catalog UI.

---

### 3.2 Application Portfolio and Architecture Intelligence

Representative products:

- CAST Highlight
- CAST Imaging

#### What they do well

CAST Highlight provides application portfolio intelligence around application health, resiliency, technical debt, cloud maturity, open-source composition, vulnerabilities, and green software insights. CAST Imaging provides architecture and dependency visualization, including code elements, data objects, transaction paths, and change impact across layers.

#### Relevance to this project

CAST is one of the closest enterprise analogs because it operates above a single repo and is designed for portfolio-level software intelligence. It is relevant for architecture review, modernization, technical debt management, and leadership reporting.

#### Gaps relative to Platform Capability Intelligence

CAST focuses on application health, architecture structure, cloud readiness, modernization, and technical debt. It does not specifically model a company-defined catalog of platform capabilities and detect whether those capabilities are reused or reinvented across tenants.

CAST can help answer:

> What is the health and structure of this application portfolio?

The proposed app answers:

> Which internal platform building blocks are tenants actually using, and where are teams duplicating platform-owned integrations?

#### Product implication

CAST is not a direct replacement. It is a relevant adjacent enterprise product. If the company already uses CAST, this project should avoid duplicating CAST-style technical debt and architecture reporting, and instead focus on the company-specific adoption/reuse gap.

---

### 3.3 Behavioral Code Analysis and Code Health

Representative product:

- CodeScene

#### What it does well

CodeScene focuses on behavioral code analysis. It combines code complexity with change history to identify hotspots, code health issues, and areas of technical debt that are likely to carry higher maintenance risk. CodeScene documentation emphasizes code churn and hotspot trends as a way to understand where software is actively evolving and where complexity is growing.

#### Relevance to this project

CodeScene is relevant because the proposed platform may eventually want to understand not only whether tenants are reinventing capabilities, but whether those custom implementations are actively changing and becoming maintenance hotspots.

For example:

> A custom Snowflake authentication implementation that is both complex and frequently changed is more important than a small custom helper that has not changed in a year.

#### Gaps relative to Platform Capability Intelligence

CodeScene focuses on code health and behavioral risk, not platform capability adoption. It is not designed to answer whether tenant repos are using a company-provided shared integration or building their own.

#### Product implication

Churn × capability reinvention is a valuable Phase 2 signal, but not an MVP requirement.

---

### 3.4 Developer Productivity and Platform Metrics Tools

Representative products / frameworks:

- DX
- LinearB
- Swarmia
- Jellyfish
- Pluralsight Flow
- DORA / SPACE-inspired internal dashboards
- platform engineering metrics frameworks

#### What they do well

These tools measure engineering productivity, developer experience, delivery flow, pull request cycle time, deployment frequency, developer satisfaction, and operational efficiency. Industry platform engineering guidance increasingly emphasizes platform adoption, utilization, developer experience, and business value as core metrics for platform teams.

#### Relevance to this project

The manager's problem is strongly aligned with platform product thinking: the platform team needs to show that its building blocks are used, reduce onboarding friction, and create measurable value.

#### Gaps relative to Platform Capability Intelligence

Developer productivity tools usually measure team flow and delivery outcomes. They do not deeply inspect code/configuration to determine capability-level adoption.

They can answer:

> Are teams shipping faster? Is PR cycle time improving? Is developer satisfaction increasing?

They usually cannot answer:

> Which repos are using the platform Snowflake Auth wrapper, and which repos rebuilt Snowflake authentication themselves?

#### Product implication

Platform Capability Intelligence should complement productivity metrics by providing a concrete adoption/reuse evidence layer.

---

### 3.5 Policy, Governance, and Compliance Tools

Representative products / tools:

- Open Policy Agent
- Conftest
- Checkov
- Snyk IaC
- Prisma Cloud
- Wiz
- Terraform Cloud policy checks

#### What they do well

These tools evaluate configuration, infrastructure-as-code, cloud resources, security posture, and policy compliance. They are useful for enforcing standards and detecting non-compliant patterns.

#### Relevance to this project

Some capability adoption checks may eventually become policy checks. For example, a platform team could define a policy that production services must use an approved secrets management pattern or standard CI/CD template.

#### Gaps relative to Platform Capability Intelligence

The proposed app should not start as a policy enforcement tool. The MVP should be read-only and advisory. Its goal is to discover adoption and reinvention patterns, not block releases or label teams as non-compliant.

#### Product implication

Policy enforcement may be a later governance layer. MVP should focus on evidence-backed insight, not enforcement.

---

### 3.6 Automated Migration and Refactoring Tools

Representative products:

- Moderne
- OpenRewrite

#### What they do well

OpenRewrite, maintained by Moderne, is an open-source automated code transformation and modernization ecosystem. It uses a compiler-accurate representation of code to apply repeatable transformations safely across codebases.

#### Relevance to this project

This category is relevant as a future execution layer. If Platform Capability Intelligence identifies that many repos have custom Snowflake authentication, a migration platform such as Moderne/OpenRewrite could eventually help migrate code toward the approved platform capability.

#### Gaps relative to Platform Capability Intelligence

Moderne/OpenRewrite focuses on code transformation and migration execution. It does not provide a cross-tenant platform capability adoption dashboard by itself.

#### Product implication

The proposed app should not generate automatic migrations in MVP. It should identify candidate reinvention patterns and provide evidence-backed recommendations. Automated migration belongs in a later phase.

---

### 3.7 AI-Assisted Engineering Tools

Representative products:

- Diffblue Cover
- AI coding agents
- AI code review assistants

#### What they do well

Diffblue Cover focuses on AI-powered Java unit test generation for enterprise codebases. AI coding and review tools help generate, review, explain, and test code.

#### Relevance to this project

This category is relevant because it shows that AI-assisted engineering tools can be viable in enterprise Java/banking-like environments when wrapped with strong validation, verification, and controlled workflows.

#### Gaps relative to Platform Capability Intelligence

AI engineering tools generally assist with code generation, testing, review, or local productivity. They do not primarily measure cross-repo adoption of internal platform capabilities.

#### Product implication

LLM usage in Platform Capability Intelligence should remain evidence-grounded and engineering-controlled. The LLM should synthesize and classify adoption/reinvention signals, not act as an unconstrained oracle.

---

## 4. Competitive Positioning Matrix

| Category | Examples | What They Solve | Gap Relative to This Project |
|---|---|---|---|
| Internal developer portals | Backstage, Cortex, OpsLevel, Port, Compass | Service catalog, ownership, scorecards, docs, self-service | Usually do not automatically detect code-level platform capability reuse or reinvention |
| Portfolio intelligence | CAST Highlight, CAST Imaging | Application health, technical debt, cloud readiness, architecture visualization | Not focused on company-specific platform capability adoption |
| Code health analytics | CodeScene | Complexity, churn, hotspots, technical debt risk | Focused on code health, not reusable platform building blocks |
| Developer productivity metrics | DX, LinearB, Swarmia, Jellyfish | Delivery flow, productivity, DevEx, DORA/SPACE metrics | Do not inspect repo evidence for capability adoption |
| Policy/compliance tools | OPA, Checkov, Snyk IaC, Prisma Cloud | Policy enforcement, IaC/security posture | Enforcement-oriented; not an advisory adoption intelligence layer |
| Automated migration | Moderne, OpenRewrite | Large-scale code transformation and migration | Execution layer, not adoption analytics |
| AI engineering tools | Diffblue, AI code review/coding agents | Code generation, testing, review support | Not designed for cross-repo platform capability adoption measurement |

---

## 5. Direct Product Gap

The proposed project fills a narrower and more internal gap:

> **A company-specific platform capability intelligence layer that detects whether approved platform building blocks are adopted, reinvented, or missing across tenant repositories, using code/config/dependency evidence and LLM-assisted classification.**

This is difficult for generic products to solve because capability definitions are highly internal:

- The approved Snowflake Auth library name is company-specific.
- The expected import pattern is company-specific.
- The CI/CD template location is company-specific.
- The logging wrapper and observability conventions are company-specific.
- Tenant/repo ownership and onboarding context are company-specific.
- Reinvention patterns depend on internal code conventions.

---

## 6. Recommended Product Positioning

Do not position the product as:

- a code quality scanner;
- a replacement for SonarQube, CodeQL, Checkmarx, Snyk, or Veracode;
- a replacement for Backstage/Cortex/OpsLevel/Port;
- a replacement for CAST or CodeScene;
- a policy enforcement engine;
- an automated migration platform.

Position it as:

> **An internal platform intelligence layer that measures adoption, reuse, and reinvention of shared platform capabilities across repos and tenants.**

Recommended statement:

> We are not replacing enterprise scanners, developer portals, or application portfolio tools. We are building a company-specific intelligence layer that uses a platform capability catalog, repository evidence, deterministic detection, and LLM-assisted classification to identify which platform capabilities are adopted, where teams are reinventing core integrations, and how platform teams can reduce onboarding friction and increase reuse.

---

## 7. MVP Differentiation

The MVP should prove a focused use case:

> Given a small set of repos and a small capability catalog, can the system identify which repos adopt a platform capability, which repos reinvent it, and what evidence supports the conclusion?

Recommended MVP scope:

- local repo archive input;
- small capability catalog;
- deterministic dependency/import/config detection;
- selected code evidence;
- LLM-assisted classification of `ADOPTED`, `REINVENTED`, `MISSING`, or `UNKNOWN`;
- evidence-backed dashboard;
- cross-repo capability adoption summary.

Deferred items:

- Bitbucket integration;
- git history / churn analysis;
- portfolio-scale reporting;
- automated migration recommendations;
- policy enforcement;
- release gates;
- full enterprise scanner integration.

---

## 8. Strategic Value for Platform Teams

This product gives platform teams better answers to questions that are currently hard to measure:

1. **Adoption**: Are tenants actually using the shared capabilities we built?
2. **Reuse**: Which building blocks are broadly reused and should receive more investment?
3. **Reinvention**: Which tenants are rebuilding the same capabilities themselves?
4. **Onboarding friction**: Where are teams avoiding platform capabilities because onboarding is too hard?
5. **Platform stickiness**: Which reusable capabilities make the platform more valuable and harder to leave?
6. **Product investment**: Which platform capabilities need better docs, templates, examples, or migration paths?

This is a product-management view of platform engineering, not just a code analysis tool.

---

## 9. Build vs. Buy Assessment

### Why not only buy an existing product?

Existing products can help with catalogs, scorecards, code health, technical debt, developer productivity, and policy enforcement. However, the specific capability adoption/reinvention signal is highly dependent on internal platform definitions and repo conventions.

A generic vendor tool is unlikely to know:

- which internal library counts as approved Snowflake Auth;
- which custom patterns indicate reinvention;
- which tenants are eligible for a capability;
- which platform team owns a reusable building block;
- which onboarding path is preferred;
- which alternative implementations are acceptable exceptions.

### Why build internally?

The most valuable logic is internal:

- capability catalog definition;
- detection rules;
- tenant/repo ownership mapping;
- evidence interpretation;
- platform-specific adoption metrics;
- internal dashboard narrative.

### Recommended approach

Build a lightweight internal app focused on capability intelligence, and integrate with existing systems later:

- use developer portals as a system of record or display layer;
- use enterprise scanners as optional evidence sources;
- use Bitbucket as a source adapter later;
- use migration tools such as OpenRewrite/Moderne only after clear reinvention patterns are identified.

---

## 10. Risks and Mitigations

| Risk | Description | Mitigation |
|---|---|---|
| False positives | System incorrectly labels a repo as reinventing a capability | Use evidence refs, confidence score, and human review in MVP |
| Capability catalog drift | Platform capability definitions become outdated | Assign owners and version capability definitions |
| Overreach into policy enforcement | Teams may resist if findings are treated as violations too early | Keep MVP advisory and non-blocking |
| LLM hallucination | LLM may infer unsupported adoption/reinvention claims | Use deterministic hard gates and evidence-backed classification |
| Scope creep | The project may expand into a full developer portal or scanner | Keep MVP focused on a few capabilities and repos |
| Poor adoption | Dashboard may be ignored if it does not answer platform leadership questions | Build demo around concrete business questions: adoption, reinvention, onboarding friction |

---

## 11. Recommended Market Analysis Conclusion

There are strong adjacent tools in the market, especially internal developer portals, service catalogs, scorecard platforms, application portfolio intelligence tools, and code health analytics products. However, the proposed Platform Capability Intelligence app addresses a narrower internal gap that these products do not fully cover: **evidence-backed measurement of platform capability adoption and reinvention across tenant repositories**.

The project is justified if it remains focused on that gap. It should not become another code quality scanner, developer portal, or enterprise architecture dashboard. Its unique value is helping platform teams understand whether their reusable building blocks are actually reducing onboarding friction, preventing duplicated integration work, and increasing platform stickiness.

---

## 12. Source Notes

The following sources were used to understand adjacent market categories:

- Backstage Software Catalog: https://backstage.io/docs/features/software-catalog/
- Cortex Scorecards: https://www.cortex.io/products/scorecard
- OpsLevel Scorecards / Service Maturity: https://www.opslevel.com/resources/when-and-why-to-use-scorecards
- Port Scorecards: https://docs.port.io/scorecards/overview/
- Atlassian Compass Software Catalog and Scorecards: https://www.atlassian.com/software/compass/software-catalog
- Datadog Internal Developer Portal Scorecards: https://docs.datadoghq.com/internal_developer_portal/scorecards/
- CAST Highlight: https://www.castsoftware.com/highlight
- CAST Imaging: https://www.castsoftware.com/imaging
- CodeScene Code Churn and Complexity Trends: https://codescene.io/docs/guides/technical/code-churn.html and https://codescene.io/docs/guides/technical/complexity-trends.html
- OpenRewrite / Moderne: https://www.moderne.ai/openrewrite and https://docs.openrewrite.org/
- Diffblue Cover: https://www.diffblue.com/
- Platform Engineering metrics discussions: https://platformengineering.org/blog/metrics-that-matter-measuring-platform-success-and-maturity
- DORA Platform Engineering Capability: https://dora.dev/capabilities/platform-engineering/
