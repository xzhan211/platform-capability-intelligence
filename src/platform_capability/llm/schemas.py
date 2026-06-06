"""Pydantic schemas for LLM step outputs (used for validation and tool definitions)."""
from __future__ import annotations
from pydantic import BaseModel


class SignalSummarySchema(BaseModel):
    capability_id: str
    adoption_pattern_summary: str
    reinvention_pattern_summary: str
    evidence_refs: list[str]
    unknowns: list[str]
    confidence: str


class RecommendationSchema(BaseModel):
    recommendation_id: str
    priority: str
    target: str
    action: str
    evidence_refs: list[str]


class InsightSchema(BaseModel):
    insight_summary: str
    recommendations: list[RecommendationSchema]
    unknowns: list[str]
