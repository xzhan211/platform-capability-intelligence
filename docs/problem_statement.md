# Problem Statement: Platform Capability Intelligence

## 1. Context

Our platform team provides shared engineering building blocks intended to make tenant onboarding easier and reduce repeated implementation across teams. Examples include Snowflake integration/authentication, platform authentication patterns, logging and observability wrappers, CI/CD templates, data access wrappers, permissioning patterns, deployment templates, and other common integration capabilities.

Today, we have tools that can evaluate code quality inside a single repository. However, the more important platform-level gap is cross-repository visibility: we do not have a strong way to measure whether our platform capabilities are actually being reused across tenants, where tenants are reinventing core integrations, and which capabilities are driving platform adoption.

The desired business outcome is to make it easy for teams to onboard and become productive on our platform, while increasing the value of staying on the platform because teams can rely on a growing set of proven, reusable capabilities instead of rebuilding them independently.

## 2. Problem

The current visibility gap is not primarily repo-level code quality. The real gap is platform capability adoption and reuse across tenants.

We need to answer questions such as:

- Which platform capabilities are available and mature enough for tenant use?
- Which tenants and repositories are using those capabilities?
- Which capabilities have broad adoption and which are underused?
- Which tenants are implementing custom versions of capabilities that the platform already provides?
- Where is onboarding friction high because reusable capabilities are missing, hard to discover, or hard to integrate?
- What capabilities make our platform easier to adopt than alternative platform options?
- If a tenant leaves the platform, which capabilities would they need to rebuild or re-implement elsewhere?

## 3. Example: Snowflake Authentication

Suppose two platform teams provide competing onboarding options:

- Team A provides Snowflake integration and authentication out of the box.
- Team B requires each tenant to implement and maintain its own Snowflake authentication logic.

A new tenant will usually choose the platform where the critical integration just works. That lowers time-to-first-value, reduces implementation risk, and decreases ongoing maintenance effort.

The reverse is also important. If a tenant considers leaving Team A's platform, the cost should be clear: they would need to rebuild Snowflake authentication, related tooling, documentation, and possibly permissioning and observability integrations on another platform.

This same logic applies across every shared capability: authentication, logging, observability, CI/CD templates, data access wrappers, permissioning, deployment templates, and other reusable platform capabilities.

## 4. Product Goal

Build a Platform Capability Intelligence application that analyzes repositories across tenants and reports how platform building blocks are adopted, reused, bypassed, or reinvented.

The application should help platform engineers, managers, and architecture reviewers understand:

- adoption of platform capabilities across tenants;
- gaps where tenants are not using recommended capabilities;
- custom implementations that duplicate platform-provided functionality;
- capability maturity and reuse patterns;
- onboarding readiness for new tenants;
- platform stickiness created by reusable shared capabilities.

## 5. Non-Goals for the First Version

The first version is not intended to:

- replace SonarQube, CodeQL, Checkmarx, Snyk, Veracode, or other scanners;
- perform release gating;
- auto-refactor tenant code;
- enforce adoption policies;
- provide complete portfolio-level governance;
- infer business ownership without repository metadata;
- claim exact replacement cost or migration effort without human review.

## 6. First Demo Objective

The first demo should prove that the system can:

1. define a small catalog of platform capabilities;
2. scan one or more repositories;
3. detect evidence of capability adoption or reinvention;
4. generate a cross-repo/tenant view of platform capability usage;
5. produce evidence-backed recommendations for platform adoption improvements;
6. show that LLM-generated insights are grounded in detected evidence and validated before being displayed.

## 7. Success Criteria

The first version is successful if it can answer a narrow but valuable question, for example:

> Across a small set of tenant repositories, who is using the platform Snowflake authentication capability, who is not, and who appears to have built a custom replacement?

Minimum success criteria:

- capability catalog exists and is versioned;
- repository ingestion works through local upload for demo;
- detection rules can identify at least one platform capability and one reinvention pattern;
- each detected signal has evidence references;
- dashboard shows adoption status by repo/tenant;
- LLM synthesis explains findings without inventing unsupported claims;
- evaluation layer validates evidence references before showing the final report.
