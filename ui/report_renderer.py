import json
import streamlit as st
from ui.styles import risk_color, severity_color, score_to_color, AGENT_ICONS


def render_report(report: dict) -> None:
    _render_hero(report["overall_risk_score"], report["risk_label"], report["findings_count"])
    _render_agent_scores(report["agent_scores"])
    _render_executive_summary(report["executive_summary"])
    _render_findings_section(report["total_findings"])
    _render_downloads(report)


# ---------------------------------------------------------------------------
# Hero score
# ---------------------------------------------------------------------------

def _render_hero(score: float, label: str, count: int) -> None:
    color = risk_color(label)
    st.markdown(
        f"""
<div class="risk-hero">
    <div class="risk-score-number" style="color:{color};">{score}/10</div>
    <div><span class="risk-badge" style="background:{color};">{label}</span></div>
    <div class="findings-count">{count} problems found</div>
</div>
""",
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Agent score cards
# ---------------------------------------------------------------------------

def _render_agent_scores(agent_scores: dict) -> None:
    agents = list(agent_scores.items())
    cols = st.columns(len(agents))
    for col, (agent_type, score) in zip(cols, agents):
        color = score_to_color(score)
        bar_pct = int((score / 10) * 100)
        icon = AGENT_ICONS.get(agent_type, "")
        with col:
            st.markdown(
                f"""
<div class="agent-card">
    <div class="agent-card-icon">{icon}</div>
    <div class="agent-card-label">{agent_type}</div>
    <div class="agent-card-score" style="color:{color};">{score}/10</div>
    <div class="score-bar-bg">
        <div class="score-bar-fill" style="width:{bar_pct}%;background:{color};"></div>
    </div>
</div>
""",
                unsafe_allow_html=True,
            )


# ---------------------------------------------------------------------------
# Executive summary
# ---------------------------------------------------------------------------

def _render_executive_summary(text: str) -> None:
    st.subheader("Executive Summary")
    st.markdown(
        f'<div class="exec-summary-box">{text}</div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Findings with filters
# ---------------------------------------------------------------------------

def _render_findings_section(findings: list[dict]) -> None:
    st.subheader(f"Findings ({len(findings)})")

    col1, col2 = st.columns(2)
    with col1:
        sev_opts = ["critical", "high", "medium", "low"]
        sel_sev = st.multiselect(
            "Severity",
            options=sev_opts,
            default=sev_opts,
            format_func=str.capitalize,
        )
    with col2:
        agent_opts = sorted({f.get("source_agent", "unknown") for f in findings})
        sel_agents = st.multiselect(
            "Agent",
            options=agent_opts,
            default=agent_opts,
            format_func=str.capitalize,
        )

    filtered = [
        f for f in findings
        if f.get("severity", "low") in sel_sev
        and f.get("source_agent", "unknown") in sel_agents
    ]

    if not filtered:
        st.info("No findings match the selected filters.")
        return

    for finding in filtered:
        _render_finding(finding)


def _render_finding(f: dict) -> None:
    sev = f.get("severity", "low")
    agent = f.get("source_agent", "unknown")
    title = f.get("title", "Untitled")
    color = severity_color(sev)
    icon = AGENT_ICONS.get(agent, "")

    label = f"[{sev.upper()}] {icon} {agent.capitalize()} — {title}"

    with st.expander(label):
        st.markdown(f.get("description", ""))

        if f.get("clause_reference"):
            st.markdown("**Problematic clause:**")
            st.markdown(
                f'<div class="clause-quote">"{f["clause_reference"]}"</div>',
                unsafe_allow_html=True,
            )

        if f.get("recommendation"):
            st.markdown("**Recommendation:**")
            st.markdown(
                f'<div class="recommendation-box">{f["recommendation"]}</div>',
                unsafe_allow_html=True,
            )

        citations = f.get("legal_citations") or []
        if citations:
            st.markdown("**Legal references:**")
            for cit in citations:
                source = cit.get("source", "?")
                excerpt = cit.get("excerpt", "")
                st.markdown(
                    f'<div class="citation-box"><strong>{source}</strong><br>'
                    f'<em>"{excerpt}"</em></div>',
                    unsafe_allow_html=True,
                )


# ---------------------------------------------------------------------------
# Downloads
# ---------------------------------------------------------------------------

def _render_downloads(report: dict) -> None:
    st.markdown("---")
    st.subheader("Download Report")
    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            label="⬇️ Download Markdown",
            data=generate_markdown(report),
            file_name="contract_analysis.md",
            mime="text/markdown",
            use_container_width=True,
        )
    with col2:
        st.download_button(
            label="⬇️ Download JSON",
            data=json.dumps(report, indent=2, ensure_ascii=False),
            file_name="contract_analysis.json",
            mime="application/json",
            use_container_width=True,
        )


def generate_markdown(report: dict) -> str:
    lines = [
        "# AI Contract Red-Teamer — Analysis Report",
        "",
        f"## Overall Risk Score: {report['overall_risk_score']}/10 — {report['risk_label']}",
        "",
        f"**Total findings:** {report['findings_count']}",
        "",
        "## Agent Scores",
        "",
    ]
    for agent, score in report["agent_scores"].items():
        lines.append(f"- **{agent.capitalize()}**: {score}/10")

    lines += [
        "",
        "## Executive Summary",
        "",
        report.get("executive_summary", ""),
        "",
        "## Findings",
        "",
    ]

    for i, f in enumerate(report["total_findings"], 1):
        sev = f.get("severity", "low").upper()
        agent = f.get("source_agent", "?").capitalize()
        title = f.get("title", "Untitled")
        lines += [
            f"### {i}. [{sev}] ({agent}) {title}",
            "",
            f.get("description", ""),
            "",
        ]
        if f.get("clause_reference"):
            lines += ["**Problematic clause:**", f'> {f["clause_reference"]}', ""]
        if f.get("recommendation"):
            lines += ["**Recommendation:**", f.get("recommendation", ""), ""]
        for cit in (f.get("legal_citations") or []):
            lines += [
                f"**Source:** {cit.get('source', '?')}",
                f'> {cit.get("excerpt", "")}',
                "",
            ]

    return "\n".join(lines)
