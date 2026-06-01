# Capability Catalog

## 1. Purpose

The Capability Catalog is the source of truth for what the platform provides. The detection pipeline cannot determine whether a repository is reusing or reinventing a platform capability unless the platform capabilities are explicitly defined.

The catalog describes:

- capability identity;
- owner team;
- expected usage patterns;
- approved libraries, templates, APIs, and configurations;
- anti-patterns that suggest reinvention;
- eligibility rules;
- evidence collection rules;
- maturity and documentation status.

## 2. Core Concepts

### Capability

A reusable platform-provided building block that tenants can adopt instead of implementing the same functionality themselves.

Examples:

- Snowflake authentication
- platform authentication wrapper
- logging and observability integration
- CI/CD template
- data access wrapper
- permissioning framework
- deployment template
- Kafka integration
- standard retry/error handling client
- secrets management pattern

### Tenant

A team, product group, service group, or application owner that uses or may use the platform.

### Repository

A source repository owned by a tenant. It is the primary unit of technical detection.

### Adoption

A repository or tenant is considered to have adopted a capability when it uses the approved platform-provided pattern, library, template, API, or configuration for that capability.

### Reinvention

A repository or tenant shows a reinvention signal when it appears to implement custom logic for a capability that the platform already provides.

### Eligibility

Not every tenant needs every capability. A repository should only be counted against a capability's adoption rate if it is eligible for that capability.

Example: A service with no Snowflake access should not lower the adoption rate of Snowflake authentication.

## 3. Capability Catalog Schema

Suggested YAML representation:

```yaml
capability_id: snowflake_auth
name: Snowflake Authentication
category: data_integration
owner_team: platform-data
status: active
maturity: beta | stable | deprecated
description: Standard platform capability for authenticating to Snowflake.
documentation_url: https://internal/docs/snowflake-auth
recommended_for:
  - services that read from or write to Snowflake
approved_usage_patterns:
  dependencies:
    - com.company.platform:snowflake-auth
  imports:
    - com.company.platform.snowflake.SnowflakeAuthClient
    - com.company.platform.snowflake.SnowflakeCredentialProvider
  config_keys:
    - platform.snowflake.auth.enabled
    - platform.snowflake.role
  templates:
    - platform-snowflake-batch-template
anti_patterns:
  class_name_patterns:
    - CustomSnowflakeAuth*
    - SnowflakeTokenManager
    - SnowflakeCredentialRefresher
  dependency_patterns:
    - net.snowflake:snowflake-jdbc without platform snowflake auth dependency
  code_patterns:
    - direct username/password Snowflake connection
    - custom OAuth token refresh logic
    - hard-coded Snowflake role or warehouse credential flow
eligibility_rules:
  include_if:
    - dependency: net.snowflake:snowflake-jdbc
    - config_key_prefix: snowflake
    - file_name_pattern: '*Snowflake*'
evidence_rules:
  collect_files:
    - pom.xml
    - build.gradle
    - application.yml
    - '*Snowflake*.java'
    - '*Auth*.java'
minimum_evidence_required:
  adoption: 1
  reinvention: 2
```

## 4. Capability Statuses

Recommended lifecycle states:

- `draft`: proposed capability, not ready for tenant adoption;
- `beta`: available to early adopters;
- `stable`: recommended for broad adoption;
- `deprecated`: should not be adopted by new tenants;
- `retired`: no longer supported.

Only `beta` and `stable` capabilities should normally be included in adoption scoring.

## 5. Detection Signal Types

### Positive Adoption Signals

Evidence that the repository is using the approved platform capability:

- approved dependency exists;
- approved import exists;
- approved config key exists;
- approved CI/CD template is referenced;
- platform-provided API/client is used;
- README or onboarding docs reference the platform capability.

### Reinvention Signals

Evidence that the repository may have custom-built a capability:

- custom class names similar to platform capability implementation;
- direct use of lower-level third-party library without platform wrapper;
- duplicated authentication, permissioning, retry, logging, or data access logic;
- configuration keys that bypass platform conventions;
- similar code patterns across multiple tenants.

### Absence Signals

Evidence that a capability is expected but not detected:

- repository appears eligible;
- no approved dependency/import/template exists;
- no custom implementation is detected;
- capability status becomes `missing` or `unknown` depending on evidence strength.

## 6. Capability Detection Status

Each repository-capability pair should be classified as one of:

- `ADOPTED`: approved platform capability usage detected;
- `CUSTOM_IMPLEMENTATION`: likely custom implementation detected;
- `MISSING`: repository appears eligible but no approved usage detected;
- `NOT_ELIGIBLE`: capability does not apply to this repository;
- `UNKNOWN`: insufficient evidence.

## 7. MVP Catalog

For the first demo, keep the catalog intentionally small.

Recommended MVP capabilities:

1. Snowflake authentication
2. logging/observability wrapper
3. CI/CD template
4. platform authentication wrapper

If time is limited, focus only on Snowflake authentication because it provides a clear adoption/reinvention story.

## 8. Versioning

The capability catalog must be versioned.

Each scan should record:

- catalog version;
- capability definitions used;
- detection rule version;
- scan timestamp.

This prevents confusion when adoption results change because rules changed rather than repositories changed.
