import streamlit as st

RISK_COLORS = {
    "CRITICAL": "#ef4444",
    "HIGH": "#f97316",
    "MEDIUM": "#eab308",
    "LOW": "#22c55e",
    "MINIMAL": "#22c55e",
}

SEVERITY_COLORS = {
    "critical": "#ef4444",
    "high": "#f97316",
    "medium": "#eab308",
    "low": "#22c55e",
}

AGENT_ICONS = {
    "legal": "⚖️",
    "financial": "💰",
    "practical": "🛠️",
}


def inject_css() -> None:
    st.markdown(
        """
<style>
/* Risk hero block */
.risk-hero {
    text-align: center;
    padding: 2rem 1rem 1.5rem;
    border-radius: 14px;
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    margin-bottom: 1.5rem;
}
.risk-score-number {
    font-size: 4.5rem;
    font-weight: 900;
    line-height: 1;
    letter-spacing: -2px;
}
.risk-badge {
    display: inline-block;
    padding: 0.3rem 1.2rem;
    border-radius: 20px;
    font-weight: 700;
    font-size: 0.95rem;
    color: white;
    margin-top: 0.5rem;
    letter-spacing: 0.08em;
}
.findings-count {
    font-size: 1rem;
    color: #64748b;
    margin-top: 0.6rem;
}

/* Agent score cards */
.agent-card {
    background: #f8fafc;
    border-radius: 12px;
    padding: 1.1rem 0.75rem;
    text-align: center;
    border: 1px solid #e2e8f0;
}
.agent-card-icon { font-size: 1.6rem; line-height: 1.2; }
.agent-card-label {
    font-weight: 700;
    font-size: 0.75rem;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    margin: 0.2rem 0;
}
.agent-card-score {
    font-size: 1.9rem;
    font-weight: 800;
    line-height: 1;
}
.score-bar-bg {
    background: #e2e8f0;
    border-radius: 4px;
    height: 7px;
    width: 100%;
    margin-top: 0.6rem;
    overflow: hidden;
}
.score-bar-fill {
    height: 7px;
    border-radius: 4px;
}

/* Executive summary */
.exec-summary-box {
    background: #f1f5f9;
    border-left: 4px solid #64748b;
    padding: 1rem 1.25rem;
    border-radius: 0 10px 10px 0;
    font-size: 0.95rem;
    line-height: 1.7;
    color: #1e293b;
    margin: 0.5rem 0 1.5rem;
}

/* Finding cards */
.severity-badge {
    display: inline-block;
    padding: 0.15rem 0.65rem;
    border-radius: 12px;
    font-weight: 700;
    font-size: 0.72rem;
    color: white;
    margin-right: 0.4rem;
    letter-spacing: 0.06em;
}
.agent-badge {
    display: inline-block;
    padding: 0.15rem 0.65rem;
    border-radius: 12px;
    font-weight: 500;
    font-size: 0.72rem;
    background: #e2e8f0;
    color: #475569;
    margin-right: 0.4rem;
}
.clause-quote {
    background: #f8fafc;
    border-left: 3px solid #cbd5e1;
    padding: 0.7rem 1rem;
    border-radius: 0 8px 8px 0;
    font-style: italic;
    font-size: 0.88rem;
    color: #475569;
    margin: 0.4rem 0 0.8rem;
}
.recommendation-box {
    background: #f0fdf4;
    border-left: 3px solid #22c55e;
    padding: 0.7rem 1rem;
    border-radius: 0 8px 8px 0;
    font-size: 0.88rem;
    color: #166534;
    margin: 0.4rem 0 0.8rem;
}
.citation-box {
    background: #eff6ff;
    border-left: 3px solid #3b82f6;
    padding: 0.7rem 1rem;
    border-radius: 0 8px 8px 0;
    font-size: 0.83rem;
    color: #1e40af;
    margin: 0.4rem 0 0.4rem;
}

/* Responsive tweaks */
@media (max-width: 640px) {
    .risk-score-number { font-size: 3rem; }
    .agent-card-score { font-size: 1.4rem; }
}
</style>
""",
        unsafe_allow_html=True,
    )


def risk_color(label: str) -> str:
    return RISK_COLORS.get(label.upper(), "#64748b")


def severity_color(severity: str) -> str:
    return SEVERITY_COLORS.get(severity.lower(), "#64748b")


def score_to_color(score: float) -> str:
    if score >= 8:
        return "#ef4444"
    if score >= 6:
        return "#f97316"
    if score >= 4:
        return "#eab308"
    return "#22c55e"
