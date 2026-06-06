from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class CapabilityStatus(str, Enum):
    DRAFT = "draft"
    BETA = "beta"
    STABLE = "stable"
    DEPRECATED = "deprecated"
    RETIRED = "retired"


class DetectionStatus(str, Enum):
    ADOPTED = "ADOPTED"
    CUSTOM_IMPLEMENTATION = "CUSTOM_IMPLEMENTATION"
    MISSING = "MISSING"
    NOT_ELIGIBLE = "NOT_ELIGIBLE"
    UNKNOWN = "UNKNOWN"
    EXEMPT = "EXEMPT"


class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class SignalType(str, Enum):
    ADOPTION = "adoption"
    REINVENTION = "reinvention"
    GENERIC_PLATFORM = "generic_platform"


class SignalWeight(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ScanStatus(str, Enum):
    CREATED = "CREATED"
    WORKSPACE_PREPARED = "WORKSPACE_PREPARED"
    DETECTION_COMPLETED = "DETECTION_COMPLETED"
    AGGREGATION_COMPLETED = "AGGREGATION_COMPLETED"
    LLM_COMPLETED = "LLM_COMPLETED"
    COMPLETED = "COMPLETED"
    COMPLETED_WITH_WARNING = "COMPLETED_WITH_WARNING"
    FAILED = "FAILED"


class EvaluationFinalStatus(str, Enum):
    ACCEPTED = "ACCEPTED"
    ACCEPTED_WITH_WARNING = "ACCEPTED_WITH_WARNING"
    RETRY_REQUIRED = "RETRY_REQUIRED"
    FAILED_FALLBACK_TO_DETERMINISTIC = "FAILED_FALLBACK_TO_DETERMINISTIC"


# ---------------------------------------------------------------------------
# Catalog models
# ---------------------------------------------------------------------------

class PatternRule(BaseModel):
    pattern: str
    weight: SignalWeight = SignalWeight.MEDIUM
    note: str = ""


class ApprovedUsagePatterns(BaseModel):
    dependencies: list[PatternRule] = []
    imports: list[PatternRule] = []
    config_keys: list[PatternRule] = []
    templates: list[PatternRule] = []


class AntiPatterns(BaseModel):
    class_name_patterns: list[PatternRule] = []
    dependency_patterns: list[PatternRule] = []
    code_patterns: list[PatternRule] = []


class EligibilityRules(BaseModel):
    include_if_dependency: list[str] = []
    include_if_import_prefix: list[str] = []
    include_if_config_key_prefix: list[str] = []
    include_if_file_pattern: list[str] = []


class EvidenceRules(BaseModel):
    collect_files: list[str] = []
    max_snippet_lines: int = 40


class MinimumEvidence(BaseModel):
    adoption: int = 1
    reinvention: int = 1


class CapabilityException(BaseModel):
    repo_id: str
    capability_id: str
    reason: str
    approved_by: str
    approved_at: str
    expires: str | None = None


class Capability(BaseModel):
    capability_id: str
    name: str
    category: str = ""
    owner_team: str = ""
    status: CapabilityStatus = CapabilityStatus.STABLE
    maturity: str = "stable"
    catalog_version: str = "1.0"
    source: str = "manual"
    description: str = ""
    documentation_url: str = ""
    recommended_for: list[str] = []
    approved_usage_patterns: ApprovedUsagePatterns = Field(default_factory=ApprovedUsagePatterns)
    anti_patterns: AntiPatterns = Field(default_factory=AntiPatterns)
    eligibility_rules: EligibilityRules = Field(default_factory=EligibilityRules)
    evidence_rules: EvidenceRules = Field(default_factory=EvidenceRules)
    minimum_evidence_required: MinimumEvidence = Field(default_factory=MinimumEvidence)


class PlatformConventions(BaseModel):
    approved_import_prefixes: list[str] = []
    approved_dependency_prefixes: list[str] = []
    config_key_prefixes: list[str] = []


class CapabilityCatalog(BaseModel):
    catalog_version: str = "1.0"
    generated_at: str = ""
    owner: str = ""
    platform_conventions: PlatformConventions = Field(default_factory=PlatformConventions)
    capabilities: list[Capability] = []
    exceptions: list[CapabilityException] = []


# ---------------------------------------------------------------------------
# Scan input models
# ---------------------------------------------------------------------------

class RepoDefinition(BaseModel):
    repo_id: str
    repo_name: str
    tenant_id: str
    archive: str
    branch: str = "main"
    commit_sha: str | None = None


class ScanManifest(BaseModel):
    scan_batch_id: str
    scan_timestamp: str = ""
    catalog_version: str = ""
    repos: list[RepoDefinition]


# ---------------------------------------------------------------------------
# Detection models
# ---------------------------------------------------------------------------

class EvidenceItem(BaseModel):
    evidence_id: str
    scan_run_id: str
    repo_id: str
    capability_id: str
    source_type: str  # dependency | import | config | code_snippet | template | generic_platform
    file_path: str
    line_start: int | None = None
    line_end: int | None = None
    content_summary: str
    raw_content: str = ""


class DetectionSignal(BaseModel):
    signal_id: str
    repo_id: str
    capability_id: str
    signal_type: SignalType
    weight: SignalWeight
    evidence_ref: str
    confidence: Confidence = Confidence.MEDIUM
    description: str = ""


class CapabilityDetectionResult(BaseModel):
    detection_id: str
    scan_run_id: str
    repo_id: str
    tenant_id: str
    capability_id: str
    status: DetectionStatus
    confidence: Confidence
    rule_version: str = "1.0"
    catalog_version: str = "1.0"
    evidence_refs: list[str] = []
    unknowns: list[str] = []
    exempt_reason: str = ""
    adoption_signals: list[DetectionSignal] = []
    reinvention_signals: list[DetectionSignal] = []


# ---------------------------------------------------------------------------
# Aggregation models
# ---------------------------------------------------------------------------

class CrossRepoMetric(BaseModel):
    metric_id: str
    scan_batch_id: str
    capability_id: str
    eligible_repo_count: int
    adopted_count: int
    custom_implementation_count: int
    missing_count: int
    unknown_count: int
    exempt_count: int
    not_eligible_count: int
    adoption_rate: float  # adopted / eligible (exempt excluded from denominator)


class RepoSummaryForLLM(BaseModel):
    repo_id: str
    tenant_id: str
    status: DetectionStatus
    confidence: Confidence
    top_evidence_refs: list[str] = []
    key_findings: list[str] = []


class CrossRepoEvidenceSummary(BaseModel):
    capability_id: str
    capability_name: str
    catalog_version: str
    scan_batch_id: str
    aggregate_metrics: CrossRepoMetric
    repo_summaries: list[RepoSummaryForLLM]
    common_reinvention_patterns: list[str] = []
    unknowns: list[str] = []
    evidence_items: list[EvidenceItem] = []
    token_count: int = 0


# ---------------------------------------------------------------------------
# LLM models
# ---------------------------------------------------------------------------

class LLMRecommendation(BaseModel):
    recommendation_id: str
    priority: str  # high | medium | low
    target: str
    action: str
    evidence_refs: list[str] = []


class SignalSummarizerOutput(BaseModel):
    capability_id: str
    adoption_pattern_summary: str
    reinvention_pattern_summary: str
    evidence_refs: list[str] = []
    unknowns: list[str] = []
    confidence: str = "high"


class InsightGeneratorOutput(BaseModel):
    insight_summary: str
    recommendations: list[LLMRecommendation] = []
    unknowns: list[str] = []


class LLMUsageMetadata(BaseModel):
    scan_run_id: str
    llm_step: str
    model_id: str
    input_tokens: int = 0
    output_tokens: int = 0
    retry_count: int = 0
    latency_ms: int = 0


# ---------------------------------------------------------------------------
# Evaluation models
# ---------------------------------------------------------------------------

class EvaluationResult(BaseModel):
    evaluation_id: str
    scan_batch_id: str
    evaluator_version: str = "1.0"
    schema_valid: bool = True
    evidence_refs_valid: bool = True
    capability_ids_valid: bool = True
    repo_ids_valid: bool = True
    hallucination_count: int = 0
    retry_count: int = 0
    final_status: EvaluationFinalStatus = EvaluationFinalStatus.ACCEPTED
    failure_reasons: list[str] = []
    warnings: list[str] = []


# ---------------------------------------------------------------------------
# Final report
# ---------------------------------------------------------------------------

class FinalReport(BaseModel):
    report_id: str
    scan_batch_id: str
    catalog_version: str
    generated_at: str
    detection_results: list[CapabilityDetectionResult]
    metrics: list[CrossRepoMetric]
    signal_summary: SignalSummarizerOutput | None = None
    insights: InsightGeneratorOutput | None = None
    evaluation: EvaluationResult | None = None
    llm_usage: list[LLMUsageMetadata] = []
    evidence_items: list[EvidenceItem] = []


# ---------------------------------------------------------------------------
# Workspace models
# ---------------------------------------------------------------------------

class FileEntry(BaseModel):
    file_id: str
    relative_path: str
    absolute_path: str
    extension: str
    size_bytes: int
    language: str = ""


class WorkspaceManifest(BaseModel):
    workspace_id: str
    repo_id: str
    workspace_path: str
    detected_languages: list[str]
    file_tree: list[FileEntry]
    dependency_files: list[str]
    config_files: list[str]
    source_files: list[str]
