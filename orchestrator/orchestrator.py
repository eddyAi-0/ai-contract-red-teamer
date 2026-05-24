import os
from anthropic import Anthropic
from dotenv import load_dotenv

from agents.legal_agent import LegalAgent
from agents.financial_agent import FinancialAgent
from agents.practical_agent import PracticalAgent

load_dotenv()

# Legal risks carry the most lasting consequences; financial are immediately tangible;
# practical risks are real but often negotiable.
_AGENT_WEIGHTS = {"legal": 0.40, "financial": 0.35, "practical": 0.25}

_SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}

_EXECUTIVE_SUMMARY_SYSTEM = (
    "You are a senior legal and business advisor briefing a non-technical executive. "
    "Write a concise executive summary (3-5 sentences, no bullet points) based on a "
    "multi-agent contract analysis. Be direct: state the main risks, their potential "
    "impact, and give a clear recommendation on whether to sign as-is, negotiate, or walk away."
)


class Orchestrator:
    def __init__(self, vectorstore=None):
        self.legal_agent = LegalAgent()
        self.financial_agent = FinancialAgent()
        self.practical_agent = PracticalAgent()
        self.client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.vectorstore = vectorstore

        if vectorstore is not None:
            for agent in (self.legal_agent, self.financial_agent, self.practical_agent):
                agent.set_vectorstore(vectorstore)

    def analyze(self, contract_text: str) -> dict:
        """
        Run all three agents sequentially, then synthesize a final report.
        Uses RAG-augmented analysis when a vectorstore is available.
        """
        if self.vectorstore is not None:
            legal = self.legal_agent.analyze_structured_with_rag(contract_text)
            financial = self.financial_agent.analyze_structured_with_rag(contract_text)
            practical = self.practical_agent.analyze_structured_with_rag(contract_text)
        else:
            legal = self.legal_agent.analyze_structured(contract_text)
            financial = self.financial_agent.analyze_structured(contract_text)
            practical = self.practical_agent.analyze_structured(contract_text)

        agent_results = [legal, financial, practical]

        overall_risk_score = self._weighted_score(agent_results)
        total_findings = self._merge_findings(agent_results)
        executive_summary = self._executive_summary(agent_results, overall_risk_score)

        return {
            "overall_risk_score": overall_risk_score,
            "risk_label": _risk_label(overall_risk_score),
            "findings_count": len(total_findings),
            "total_findings": total_findings,
            "agent_scores": {r["agent_type"]: r["risk_score"] for r in agent_results},
            "agent_summaries": {r["agent_type"]: r.get("summary", "") for r in agent_results},
            "executive_summary": executive_summary,
        }

    def _weighted_score(self, results: list[dict]) -> float:
        score = sum(
            r.get("risk_score", 0) * _AGENT_WEIGHTS.get(r.get("agent_type", ""), 0)
            for r in results
        )
        return round(score, 1)

    def _merge_findings(self, results: list[dict]) -> list[dict]:
        findings = []
        for result in results:
            for finding in result.get("findings", []):
                findings.append({**finding, "source_agent": result.get("agent_type", "unknown")})
        findings.sort(key=lambda f: _SEVERITY_ORDER.get(f.get("severity", "low"), 3))
        return findings

    def _executive_summary(self, results: list[dict], overall_score: float) -> str:
        agent_summaries = "\n".join(
            f"- {r['agent_type'].upper()} (score {r.get('risk_score', 0)}/10): "
            f"{r.get('summary', 'No summary available.')}"
            for r in results
        )
        response = self.client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=512,
            system=_EXECUTIVE_SUMMARY_SYSTEM,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Overall risk score: {overall_score}/10 "
                        f"({_risk_label(overall_score)})\n\n"
                        f"Agent findings:\n{agent_summaries}\n\n"
                        "Write the executive summary."
                    ),
                }
            ],
        )
        return response.content[0].text.strip()


def _risk_label(score: float) -> str:
    if score >= 8:
        return "CRITICAL"
    if score >= 6:
        return "HIGH"
    if score >= 4:
        return "MEDIUM"
    if score >= 2:
        return "LOW"
    return "MINIMAL"
