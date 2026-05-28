import os
import tempfile
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from orchestrator.orchestrator import Orchestrator, _risk_label
from rag.vectorstore import VectorStore
from utils.pdf_parser import extract_text_from_pdf
from ui.report_renderer import render_report
from ui.styles import inject_css

load_dotenv()

GITHUB_URL = "https://github.com/eddyAi-0/ai-contract-red-teamer"

CONTRATTO_ESEMPIO = """
CONTRATTO DI ABBONAMENTO SERVIZI CLOUD

Art. 1 - Oggetto
Il fornitore (CloudCorp Inc., con sede in Delaware, USA) fornisce servizi cloud al cliente.

Art. 2 - Dati personali
Il fornitore raccoglie e tratta tutti i dati del cliente per finalità di marketing,
profilazione, e condivisione con terze parti partner commerciali. Il cliente
acconsente automaticamente all'accettazione del presente contratto.

Art. 3 - Modifiche unilaterali
CloudCorp si riserva il diritto di modificare in qualsiasi momento e senza
preavviso i termini del presente contratto, incluso il prezzo del servizio.

Art. 4 - Costi
Il costo base è di 100€/mese. Sono inoltre previsti costi aggiuntivi per
traffico dati eccedente, supporto premium, backup, ripristino, e altri servizi
accessori non meglio specificati.

Art. 5 - Penali
In caso di ritardo nei pagamenti, si applicheranno interessi pari al 15% mensile
composto, oltre a una penale fissa di 500€ per ogni giorno di ritardo.

Art. 6 - Rinnovo
Il contratto si rinnova automaticamente per ulteriori 24 mesi salvo disdetta
scritta inviata via raccomandata almeno 90 giorni prima della scadenza.

Art. 7 - Foro competente
Per ogni controversia è competente esclusivamente il foro di Wilmington,
Delaware, USA, secondo la legge dello Stato del Delaware.

Art. 8 - Limitazione responsabilità
Il fornitore non è responsabile per alcun tipo di danno, diretto o indiretto.
La responsabilità massima è limitata a 10€.

Art. 9 - Obblighi del cliente
Il cliente si impegna a garantire uptime del 100% delle proprie infrastrutture
collegate, a fornire reportistica mensile dettagliata, e a risolvere
qualsiasi incidente entro 1 ora dalla notifica.

Art. 10 - Recesso
Il cliente può recedere solo previo pagamento di una penale pari al 200%
del valore residuo del contratto.
"""


# ---------------------------------------------------------------------------
# Cached resources
# ---------------------------------------------------------------------------

@st.cache_resource
def get_vectorstore() -> "VectorStore | None":
    if not os.getenv("VOYAGE_API_KEY"):
        return None
    try:
        vs = VectorStore()
        # Probe the collection immediately — raises if chroma_db was rebuilt
        # while the cache was alive, so we fail fast here rather than mid-analysis
        vs.collection.count()
        return vs if vs.is_indexed() else None
    except Exception:
        return None


def _safe_vectorstore() -> "VectorStore | None":
    """Return a working VectorStore, clearing the cache if the stored one is stale."""
    vs = get_vectorstore()
    if vs is None:
        return None
    try:
        vs.collection.count()  # probe: raises if collection UUID no longer exists
        return vs
    except Exception:
        get_vectorstore.clear()
        return get_vectorstore()


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

def render_sidebar() -> None:
    with st.sidebar:
        st.markdown("## ⚖️ AI Contract\nRed-Teamer")
        st.markdown(
            "Upload a PDF contract. Three AI agents analyze it in sequence "
            "and produce a risk report with score **0–10**."
        )
        st.markdown(f"[📦 GitHub]({GITHUB_URL})", unsafe_allow_html=False)

        gdpr_path = Path(__file__).parent / "rag" / "documents" / "CELEX_32016R0679_EN_TXT.pdf"
        if gdpr_path.exists():
            vs = _safe_vectorstore()
            rag_label = "✅ RAG active" if vs else "⚠️ RAG not indexed"
            st.markdown("---")
            st.caption(f"📄 GDPR (EU Reg. 2016/679)\n{rag_label}")

        if "report" in st.session_state:
            st.markdown("---")
            if st.button("🔄 New analysis", use_container_width=True):
                for key in ("report", "analyzing", "contract_text"):
                    st.session_state.pop(key, None)
                st.rerun()


# ---------------------------------------------------------------------------
# Upload state
# ---------------------------------------------------------------------------

def render_upload_state() -> None:
    st.title("⚖️ AI Contract Red-Teamer")
    st.markdown(
        "Upload a **PDF** contract or Terms of Service. "
        "Three specialized agents identify dangerous clauses, "
        "ambiguities, and hidden traps — before you sign."
    )

    missing = [k for k in ("ANTHROPIC_API_KEY",) if not os.getenv(k)]
    if missing:
        st.error(
            f"⚠️ Missing environment variables: `{', '.join(missing)}`.\n\n"
            "Create a `.env` file with the required API keys (see `.env.example`)."
        )
        return

    st.markdown("---")
    tab_pdf, tab_sample = st.tabs(["📄 Upload PDF", "📋 Sample contract"])

    with tab_pdf:
        uploaded = st.file_uploader(
            "Select a PDF file",
            type=["pdf"],
            help="Supports contracts, ToS, NDAs, and commercial agreements.",
        )

        if uploaded:
            st.caption(f"Selected file: **{uploaded.name}** ({uploaded.size // 1024} KB)")

        st.info(
            "ℹ️ Analysis takes ~30–60 seconds and costs ~$0.10 in API calls.",
        )

        if st.button(
            "🔍 Analyze contract",
            type="primary",
            disabled=uploaded is None,
            use_container_width=True,
        ):
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(uploaded.read())
                tmp_path = tmp.name
            try:
                text, was_truncated = extract_text_from_pdf(tmp_path)
            except Exception as e:
                st.error(f"PDF read error: {e}")
                return
            finally:
                Path(tmp_path).unlink(missing_ok=True)

            if not text.strip():
                st.error("No text extracted from PDF. The file may be scanned or password-protected.")
                return

            if was_truncated:
                st.info("ℹ️ Long document: analyzed the first 25,000 characters (~7 pages)")

            _start_analysis(text)

    with tab_sample:
        st.markdown(
            "A deliberately problematic contract for testing the system. "
            "Contains **GDPR violations**, disproportionate penalties, and predatory clauses."
        )
        with st.expander("Show sample contract text"):
            st.code(CONTRATTO_ESEMPIO.strip(), language="text")

        st.info("ℹ️ Analysis takes ~30–60 seconds and costs ~$0.10 in API calls.")

        if st.button("🔍 Analyze sample contract", type="primary", use_container_width=True):
            _start_analysis(CONTRATTO_ESEMPIO)


def _start_analysis(text: str) -> None:
    st.session_state.contract_text = text
    st.session_state.analyzing = True
    st.rerun()


# ---------------------------------------------------------------------------
# Analyzing state — runs agents sequentially with live progress
# ---------------------------------------------------------------------------

def render_analyzing_state() -> None:
    contract_text = st.session_state.get("contract_text", "")
    if not contract_text:
        st.session_state.analyzing = False
        st.rerun()
        return

    st.title("🔍 Analyzing...")
    st.markdown("Agents are reviewing the contract. Please do not close this page.")

    progress = st.progress(0)

    p_text    = st.empty()
    p_legal   = st.empty()
    p_fin     = st.empty()
    p_prac    = st.empty()
    p_summary = st.empty()

    p_text.markdown("✅ Text extracted")
    progress.progress(10)

    vs = _safe_vectorstore()
    if vs is None and os.getenv("VOYAGE_API_KEY"):
        st.caption("⚠️ RAG unavailable — analysis without GDPR normative references.")

    def analyze(agent):
        if vs:
            return agent.analyze_structured_with_rag(contract_text)
        return agent.analyze_structured(contract_text)

    try:
        orchestrator = Orchestrator(vectorstore=vs)

        p_legal.markdown("⏳ **Legal Agent** — analyzing legal clauses...")
        legal = analyze(orchestrator.legal_agent)
        p_legal.markdown(
            f"✅ **Legal Agent** done — score: **{legal.get('risk_score', '?')}/10**"
        )
        progress.progress(40)

        p_fin.markdown("⏳ **Financial Agent** — analyzing financial clauses...")
        financial = analyze(orchestrator.financial_agent)
        p_fin.markdown(
            f"✅ **Financial Agent** done — score: **{financial.get('risk_score', '?')}/10**"
        )
        progress.progress(65)

        p_prac.markdown("⏳ **Practical Agent** — analyzing practical clauses...")
        practical = analyze(orchestrator.practical_agent)
        p_prac.markdown(
            f"✅ **Practical Agent** done — score: **{practical.get('risk_score', '?')}/10**"
        )
        progress.progress(85)

        p_summary.markdown("⏳ **Orchestrator** — generating executive summary...")
        results = [legal, financial, practical]
        overall = orchestrator._weighted_score(results)
        findings = orchestrator._merge_findings(results)
        summary = orchestrator._executive_summary(results, overall)

        report = {
            "overall_risk_score": overall,
            "risk_label": _risk_label(overall),
            "findings_count": len(findings),
            "total_findings": findings,
            "agent_scores": {r["agent_type"]: r["risk_score"] for r in results},
            "agent_summaries": {r["agent_type"]: r.get("summary", "") for r in results},
            "executive_summary": summary,
        }

        p_summary.markdown("✅ **Executive summary** generated")
        progress.progress(100)

        st.session_state.report = report
        st.session_state.analyzing = False
        st.rerun()

    except Exception as exc:
        st.error(f"❌ Analysis error: {exc}")
        st.markdown("Check your API keys in the `.env` file and try again.")
        if st.button("↩️ Back to upload"):
            st.session_state.analyzing = False
            st.rerun()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    st.set_page_config(
        page_title="AI Contract Red-Teamer",
        page_icon="⚖️",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    inject_css()
    render_sidebar()

    if "report" in st.session_state:
        st.title("📋 Contract Analysis Report")
        render_report(st.session_state.report)
    elif st.session_state.get("analyzing"):
        render_analyzing_state()
    else:
        render_upload_state()


if __name__ == "__main__":
    main()
