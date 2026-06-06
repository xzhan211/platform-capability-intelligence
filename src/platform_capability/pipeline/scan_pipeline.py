from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from platform_capability.catalog.loader import load_catalog
from platform_capability.classification.aggregator import CrossRepoAggregator
from platform_capability.classification.classifier import CapabilityUsageClassifier
from platform_capability.config import settings
from platform_capability.detectors.code_pattern import CodePatternDetector
from platform_capability.detectors.dependency import DependencyDetector
from platform_capability.detectors.import_detector import ImportDetector
from platform_capability.detectors.namespace import PlatformNamespaceDetector
from platform_capability.llm.pipeline import LLMPipeline
from platform_capability.models import (
    CapabilityDetectionResult, EvidenceItem, FinalReport,
    ScanManifest, CapabilityCatalog, DetectionStatus,
    CrossRepoMetric, CrossRepoEvidenceSummary,
)
from platform_capability.workspace.manager import WorkspaceManager
from platform_capability.workspace.manifest import load_manifest


class ScanPipeline:
    def __init__(self):
        self._classifier = CapabilityUsageClassifier()
        self._aggregator = CrossRepoAggregator()
        self._llm = LLMPipeline()

    def run(self, manifest_path: str, catalog_path: str) -> FinalReport:
        manifest = load_manifest(manifest_path)
        catalog = load_catalog(catalog_path)
        scan_batch_id = manifest.scan_batch_id
        generated_at = datetime.now(timezone.utc).isoformat()

        workspace_mgr = WorkspaceManager()

        # Filter active capabilities
        active_caps = [
            c for c in catalog.capabilities
            if c.status.value in ("beta", "stable")
        ]

        # Collect all detectors
        dep_detector = DependencyDetector()
        imp_detector = ImportDetector()
        code_detector = CodePatternDetector()
        ns_detector = PlatformNamespaceDetector(catalog.platform_conventions)

        all_results: list[CapabilityDetectionResult] = []
        all_evidence: dict[str, EvidenceItem] = {}
        all_metrics: list[CrossRepoMetric] = []

        # Per-capability, per-repo detection
        cap_repo_results: dict[str, list[CapabilityDetectionResult]] = {
            cap.capability_id: [] for cap in active_caps
        }

        try:
            for repo_def in manifest.repos:
                scan_run_id = f"run-{uuid.uuid4().hex[:12]}"
                print(f"  Preparing workspace: {repo_def.repo_id}")
                workspace = workspace_mgr.prepare(repo_def.repo_id, repo_def.archive)

                for cap in active_caps:
                    signals, items = [], []

                    # Run all detectors
                    for detector in [dep_detector, imp_detector, code_detector, ns_detector]:
                        try:
                            s, i = detector.detect(workspace, cap, scan_run_id)
                            signals.extend(s)
                            items.extend(i)
                        except Exception as e:
                            print(f"    Detector {detector.__class__.__name__} error: {e}")

                    for item in items:
                        all_evidence[item.evidence_id] = item

                    result = self._classifier.classify(
                        workspace, cap, signals, items, catalog, scan_run_id
                    )
                    result.tenant_id = repo_def.tenant_id
                    cap_repo_results[cap.capability_id].append(result)
                    all_results.append(result)

        finally:
            workspace_mgr.cleanup()

        # Aggregate per capability
        signal_summaries = []
        insight_outputs = []
        eval_results = []
        usage_records = []

        for cap in active_caps:
            results = cap_repo_results[cap.capability_id]
            metric, ev_summary = self._aggregator.aggregate(
                results, cap, scan_batch_id, all_evidence,
                max_evidence_tokens=settings.max_evidence_tokens,
            )
            all_metrics.append(metric)

            # LLM pipeline
            signal_out, insight_out, eval_result, usage = self._llm.run(
                ev_summary, f"run-{uuid.uuid4().hex[:8]}", scan_batch_id
            )
            if signal_out:
                signal_summaries.append(signal_out)
            if insight_out:
                insight_outputs.append(insight_out)
            eval_results.append(eval_result)
            usage_records.extend(usage)

        return FinalReport(
            report_id=f"report-{uuid.uuid4().hex[:12]}",
            scan_batch_id=scan_batch_id,
            catalog_version=catalog.catalog_version,
            generated_at=generated_at,
            detection_results=all_results,
            metrics=all_metrics,
            signal_summary=signal_summaries[0] if signal_summaries else None,
            insights=insight_outputs[0] if insight_outputs else None,
            evaluation=eval_results[0] if eval_results else None,
            llm_usage=usage_records,
            evidence_items=list(all_evidence.values()),
        )


def run_scan(manifest_path: str, catalog_path: str, output_dir: str) -> str:
    """Run a full scan and save report. Returns the report file path."""
    pipeline = ScanPipeline()
    report = pipeline.run(manifest_path, catalog_path)

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    report_path = out / f"report-{report.scan_batch_id}.json"
    report_path.write_text(report.model_dump_json(indent=2))

    return str(report_path)
