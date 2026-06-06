"""Platform Capability Intelligence — Streamlit Dashboard"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import streamlit as st

st.set_page_config(
    page_title="Platform Capability Intelligence",
    page_icon="🔍",
    layout="wide",
)

STATUS_COLORS = {
    "ADOPTED": "🟢",
    "CUSTOM_IMPLEMENTATION": "🟡",
    "MISSING": "🟠",
    "NOT_ELIGIBLE": "⚫",
    "UNKNOWN": "🔵",
    "EXEMPT": "⚪",
}

STATUS_LABELS = {
    "ADOPTED": "Adopted",
    "CUSTOM_IMPLEMENTATION": "Custom Impl",
    "MISSING": "Missing",
    "NOT_ELIGIBLE": "Not Eligible",
    "UNKNOWN": "Unknown",
    "EXEMPT": "Exempt",
}


def load_report(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


def find_latest_report(output_dir: str) -> str | None:
    p = Path(output_dir)
    if not p.exists():
        return None
    reports = sorted(p.glob("report-*.json"), key=lambda x: x.stat().st_mtime, reverse=True)
    return str(reports[0]) if reports else None


def run_scan(manifest: str, catalog: str) -> str:
    """Run scan via CLI and return report path."""
    output_dir = tempfile.mkdtemp(prefix="pci-output-")
    result = subprocess.run(
        [sys.executable, "-m", "platform_capability.cli", "scan",
         "--manifest", manifest, "--catalog", catalog, "--output", output_dir],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr or result.stdout)
    reports = list(Path(output_dir).glob("report-*.json"))
    if not reports:
        raise RuntimeError("No report generated")
    return str(reports[0])


# ── Sidebar ─────────────────────────────────────────────────────────────────

st.sidebar.title("🔍 Platform Capability Intelligence")
page = st.sidebar.radio(
    "Navigate",
    ["Scan", "Platform Catalog", "Adoption Overview", "Repo Matrix", "Evidence Drill-Down", "LLM Insights"],
)

# Persist report in session
if "report" not in st.session_state:
    st.session_state.report = None
if "report_path" not in st.session_state:
    st.session_state.report_path = None

# ── Pages ────────────────────────────────────────────────────────────────────

if page == "Scan":
    st.title("Run a Capability Scan")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Quick Demo Scan")
        demo_manifest = str(Path(__file__).parent.parent / "demo/manifest/scan_manifest.yaml")
        demo_catalog = str(Path(__file__).parent.parent / "demo/manifest/platform_manifest.yaml")
        st.code(f"Manifest : {demo_manifest}\nCatalog  : {demo_catalog}", language="text")

        if st.button("▶ Run Demo Scan", type="primary"):
            with st.spinner("Scanning 5 demo repos..."):
                try:
                    path = run_scan(demo_manifest, demo_catalog)
                    st.session_state.report_path = path
                    st.session_state.report = load_report(path)
                    st.success(f"✅ Scan complete — navigate to Adoption Overview")
                except Exception as e:
                    st.error(f"Scan failed: {e}")

    with col2:
        st.subheader("Custom Scan")
        manifest_path = st.text_input("Manifest path")
        catalog_path = st.text_input("Catalog path")
        if st.button("Run Custom Scan") and manifest_path and catalog_path:
            with st.spinner("Scanning..."):
                try:
                    path = run_scan(manifest_path, catalog_path)
                    st.session_state.report_path = path
                    st.session_state.report = load_report(path)
                    st.success("✅ Scan complete")
                except Exception as e:
                    st.error(f"Scan failed: {e}")

    st.divider()
    st.subheader("Load Existing Report")
    report_file = st.text_input("Report JSON path")
    if st.button("Load") and report_file:
        try:
            st.session_state.report = load_report(report_file)
            st.session_state.report_path = report_file
            st.success("Report loaded")
        except Exception as e:
            st.error(str(e))

elif page == "Platform Catalog":
    st.title("📦 Platform Capabilities")

    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
    from platform_capability.catalog.loader import load_catalog

    demo_platform_manifest = str(Path(__file__).parent.parent / "demo/manifest/platform_manifest.yaml")
    try:
        catalog = load_catalog(demo_platform_manifest)
    except Exception as e:
        st.error(f"Failed to load catalog: {e}")
        st.stop()

    st.caption(f"Source: `{demo_platform_manifest}` · {len(catalog.capabilities)} capability(ies) · version {catalog.catalog_version}")

    for cap in catalog.capabilities:
        status_icon = {"stable": "🟢", "beta": "🟡", "deprecated": "🔴"}.get(cap.status.value, "⚫")
        with st.expander(f"{status_icon} **{cap.name}** — `{cap.capability_id}`", expanded=True):
            col1, col2, col3 = st.columns(3)
            col1.markdown(f"**Status:** {cap.status.value}")
            col2.markdown(f"**Category:** {cap.category or '—'}")
            col3.markdown(f"**Owner:** {cap.owner_team or '—'}")

            if cap.description:
                st.write(cap.description.strip())

            if cap.documentation_url:
                st.markdown(f"[Documentation]({cap.documentation_url})")

            if cap.recommended_for:
                st.markdown("**Recommended for:** " + ", ".join(cap.recommended_for))

            col_a, col_b = st.columns(2)
            with col_a:
                dep_patterns = [p.pattern for p in cap.approved_usage_patterns.dependencies]
                imp_patterns = [p.pattern for p in cap.approved_usage_patterns.imports]
                if dep_patterns or imp_patterns:
                    st.markdown("**Approved Usage Patterns**")
                    if dep_patterns:
                        st.caption("Dependencies: " + ", ".join(f"`{p}`" for p in dep_patterns))
                    if imp_patterns:
                        st.caption("Imports: " + ", ".join(f"`{p}`" for p in imp_patterns))

            with col_b:
                elig = cap.eligibility_rules
                elig_deps = elig.include_if_dependency
                elig_imp = elig.include_if_import_prefix
                if elig_deps or elig_imp:
                    st.markdown("**Eligibility Rules**")
                    if elig_deps:
                        st.caption("If dependency: " + ", ".join(f"`{d}`" for d in elig_deps))
                    if elig_imp:
                        st.caption("If import prefix: " + ", ".join(f"`{i}`" for i in elig_imp))

elif page == "Adoption Overview":
    st.title("📊 Adoption Overview")

    if not st.session_state.report:
        st.info("Run a scan first (go to Scan page).")
        st.stop()

    report = st.session_state.report
    metrics = report.get("metrics", [])

    for m in metrics:
        st.subheader(f"Capability: {m['capability_id']}")

        eligible = m["eligible_repo_count"]
        adopted = m["adopted_count"]
        custom = m["custom_implementation_count"]
        missing = m["missing_count"]
        unknown = m["unknown_count"]
        exempt = m["exempt_count"]
        not_eligible = m["not_eligible_count"]
        rate = m["adoption_rate"] * 100

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Adoption Rate", f"{rate:.0f}%", help="adopted / eligible (EXEMPT excluded)")
        c2.metric("🟢 Adopted", adopted)
        c3.metric("🟡 Custom Impl", custom)
        c4.metric("🟠 Missing", missing)
        c5.metric("🔵 Unknown", unknown)

        if exempt or not_eligible:
            e1, e2 = st.columns(2)
            e1.metric("⚪ Exempt", exempt)
            e2.metric("⚫ Not Eligible", not_eligible)

        st.caption(f"Adoption rate denominator: {eligible} eligible repo(s) (excludes EXEMPT and NOT_ELIGIBLE)")

elif page == "Repo Matrix":
    st.title("🗂️ Repository × Capability Matrix")

    if not st.session_state.report:
        st.info("Run a scan first (go to Scan page).")
        st.stop()

    report = st.session_state.report
    results = report.get("detection_results", [])

    # Build matrix: repo -> capability -> result
    repos = sorted({r["repo_id"] for r in results})
    capabilities = sorted({r["capability_id"] for r in results})
    matrix: dict[str, dict[str, dict]] = {repo: {} for repo in repos}
    for r in results:
        matrix[r["repo_id"]][r["capability_id"]] = r

    # Display
    header = ["Repo", "Tenant"] + capabilities
    rows = []
    for repo in repos:
        tenant = next((r["tenant_id"] for r in results if r["repo_id"] == repo), "")
        row = [repo, tenant]
        for cap in capabilities:
            det = matrix[repo].get(cap)
            if det:
                icon = STATUS_COLORS.get(det["status"], "❓")
                label = STATUS_LABELS.get(det["status"], det["status"])
                row.append(f"{icon} {label}")
            else:
                row.append("—")
        rows.append(row)

    import pandas as pd
    df = pd.DataFrame(rows, columns=header)
    st.dataframe(df, width='stretch', hide_index=True)

    st.divider()
    st.subheader("Legend")
    for status, icon in STATUS_COLORS.items():
        st.write(f"{icon} **{STATUS_LABELS[status]}** — {status}")

elif page == "Evidence Drill-Down":
    st.title("🔎 Evidence Drill-Down")

    if not st.session_state.report:
        st.info("Run a scan first (go to Scan page).")
        st.stop()

    report = st.session_state.report
    results = report.get("detection_results", [])
    evidence_map = {e["evidence_id"]: e for e in report.get("evidence_items", [])}

    repos = sorted({r["repo_id"] for r in results})
    selected_repo = st.selectbox("Select repository", repos)

    repo_results = [r for r in results if r["repo_id"] == selected_repo]

    for result in repo_results:
        status = result["status"]
        icon = STATUS_COLORS.get(status, "❓")
        conf = result.get("confidence", "")
        cap = result["capability_id"]

        with st.expander(f"{icon} {cap} — **{STATUS_LABELS.get(status, status)}** ({conf} confidence)", expanded=True):
            if result.get("unknowns"):
                st.warning("Unknowns: " + "; ".join(result["unknowns"]))

            if result.get("exempt_reason"):
                st.info(f"Exempt: {result['exempt_reason']}")

            ev_refs = result.get("evidence_refs", [])
            if not ev_refs:
                st.write("_No evidence collected for this classification._")
                continue

            st.write(f"**{len(ev_refs)} evidence item(s)**")
            for ev_id in ev_refs:
                ev = evidence_map.get(ev_id)
                if not ev:
                    continue
                src = ev.get("source_type", "")
                fp = ev.get("file_path", "")
                summary = ev.get("content_summary", "")
                raw = ev.get("raw_content", "")

                with st.container():
                    st.markdown(f"**`{fp}`** · _{src}_")
                    st.caption(summary)
                    if raw and raw.strip():
                        st.code(raw, language="python")
                    st.divider()

elif page == "LLM Insights":
    st.title("💡 LLM Platform Insights")

    if not st.session_state.report:
        st.info("Run a scan first (go to Scan page).")
        st.stop()

    report = st.session_state.report

    # Evaluation status
    ev = report.get("evaluation")
    if ev:
        status = ev.get("final_status", "")
        color = "green" if status == "ACCEPTED" else ("orange" if "WARNING" in status else "red")
        st.markdown(f"**Validation Status:** :{color}[{status}]")
        if ev.get("warnings"):
            for w in ev["warnings"]:
                st.warning(w)
        if ev.get("failure_reasons"):
            for f in ev["failure_reasons"]:
                st.error(f)
        st.divider()

    # Signal summary
    sig = report.get("signal_summary")
    if sig:
        st.subheader("Signal Summary")
        st.write(f"**Adoption pattern:** {sig.get('adoption_pattern_summary', '')}")
        st.write(f"**Reinvention pattern:** {sig.get('reinvention_pattern_summary', '')}")
        if sig.get("unknowns"):
            st.write(f"**Unknowns:** {'; '.join(sig['unknowns'])}")
        st.divider()

    # Insights
    ins = report.get("insights")
    if ins:
        st.subheader("Platform Insight")
        st.info(ins.get("insight_summary", ""))

        recs = ins.get("recommendations", [])
        if recs:
            st.subheader("Recommended Actions")
            for rec in recs:
                priority = rec.get("priority", "medium")
                icon = "🔴" if priority == "high" else ("🟡" if priority == "medium" else "🟢")
                with st.container():
                    st.markdown(f"{icon} **[{priority.upper()}]** `{rec['target']}`")
                    st.write(rec["action"])
                    if rec.get("evidence_refs"):
                        st.caption(f"Evidence refs: {', '.join(rec['evidence_refs'])}")
                    st.divider()

    # LLM usage
    usage = report.get("llm_usage", [])
    if usage:
        st.subheader("LLM Usage")
        import pandas as pd
        df = pd.DataFrame([
            {
                "Step": u.get("llm_step"),
                "Model": u.get("model_id"),
                "Input tokens": u.get("input_tokens"),
                "Output tokens": u.get("output_tokens"),
                "Retries": u.get("retry_count"),
                "Latency ms": u.get("latency_ms"),
            }
            for u in usage
        ])
        st.dataframe(df, width='stretch', hide_index=True)
    else:
        st.info("No LLM insight available. Run a scan to generate insights.")
