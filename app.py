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
        return vs if vs.is_indexed() else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

def render_sidebar() -> None:
    with st.sidebar:
        st.markdown("## ⚖️ AI Contract\nRed-Teamer")
        st.markdown(
            "Carica un contratto PDF. Tre agenti AI lo analizzano in sequenza "
            "e producono un risk report con score **0–10**."
        )
        st.markdown(f"[📦 GitHub]({GITHUB_URL})", unsafe_allow_html=False)

        gdpr_path = Path(__file__).parent / "rag" / "documents" / "CELEX_32016R0679_IT_TXT.pdf"
        if gdpr_path.exists():
            vs = get_vectorstore()
            rag_label = "✅ RAG attivo" if vs else "⚠️ RAG non indicizzato"
            st.markdown("---")
            st.caption(f"📄 GDPR (Reg. UE 2016/679)\n{rag_label}")

        if "report" in st.session_state:
            st.markdown("---")
            if st.button("🔄 Nuova analisi", use_container_width=True):
                for key in ("report", "analyzing", "contract_text"):
                    st.session_state.pop(key, None)
                st.rerun()


# ---------------------------------------------------------------------------
# Upload state
# ---------------------------------------------------------------------------

def render_upload_state() -> None:
    st.title("⚖️ AI Contract Red-Teamer")
    st.markdown(
        "Carica un **PDF** di contratto o Termini di Servizio. "
        "Tre agenti specializzati identificano clausole pericolose, "
        "ambiguità e trappole — prima che tu firmi."
    )

    missing = [k for k in ("ANTHROPIC_API_KEY",) if not os.getenv(k)]
    if missing:
        st.error(
            f"⚠️ Variabili d'ambiente mancanti: `{', '.join(missing)}`.\n\n"
            "Crea un file `.env` con le API key richieste (vedi `.env.example`)."
        )
        return

    st.markdown("---")
    tab_pdf, tab_sample = st.tabs(["📄 Carica PDF", "📋 Contratto d'esempio"])

    with tab_pdf:
        uploaded = st.file_uploader(
            "Seleziona un file PDF",
            type=["pdf"],
            help="Supporta contratti, ToS, NDA, accordi commerciali.",
        )

        if uploaded:
            st.caption(f"File selezionato: **{uploaded.name}** ({uploaded.size // 1024} KB)")

        st.info(
            "ℹ️ L'analisi richiede circa 30–60 secondi e consuma ~$0.10 di API.",
        )

        if st.button(
            "🔍 Analizza contratto",
            type="primary",
            disabled=uploaded is None,
            use_container_width=True,
        ):
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(uploaded.read())
                tmp_path = tmp.name
            try:
                text = extract_text_from_pdf(tmp_path)
            except Exception as e:
                st.error(f"Errore nella lettura del PDF: {e}")
                return
            finally:
                Path(tmp_path).unlink(missing_ok=True)

            if not text.strip():
                st.error("Nessun testo estratto dal PDF. Il file potrebbe essere scansionato o protetto.")
                return

            page_count = text.count("\f") + 1
            if page_count > 50:
                st.warning(f"Il PDF ha ~{page_count} pagine. L'analisi potrebbe essere incompleta.")

            _start_analysis(text)

    with tab_sample:
        st.markdown(
            "Contratto volutamente problematico per testare il sistema. "
            "Contiene **violazioni GDPR**, penali sproporzionate e clausole capestro."
        )
        with st.expander("Mostra testo del contratto d'esempio"):
            st.code(CONTRATTO_ESEMPIO.strip(), language="text")

        st.info("ℹ️ L'analisi richiede circa 30–60 secondi e consuma ~$0.10 di API.")

        if st.button("🔍 Analizza contratto d'esempio", type="primary", use_container_width=True):
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

    st.title("🔍 Analisi in corso...")
    st.markdown("Gli agenti stanno esaminando il contratto. Non chiudere questa pagina.")

    progress = st.progress(0)

    p_text    = st.empty()
    p_legal   = st.empty()
    p_fin     = st.empty()
    p_prac    = st.empty()
    p_summary = st.empty()

    p_text.markdown("✅ Testo estratto e pronto")
    progress.progress(10)

    vs = get_vectorstore()
    if vs is None and os.getenv("VOYAGE_API_KEY"):
        st.caption("⚠️ RAG non disponibile — analisi senza citazioni normative GDPR.")

    def analyze(agent):
        if vs:
            return agent.analyze_structured_with_rag(contract_text)
        return agent.analyze_structured(contract_text)

    try:
        orchestrator = Orchestrator(vectorstore=vs)

        p_legal.markdown("⏳ **Legal Agent** — analisi clausole legali...")
        legal = analyze(orchestrator.legal_agent)
        p_legal.markdown(
            f"✅ **Legal Agent** completato — score: **{legal.get('risk_score', '?')}/10**"
        )
        progress.progress(40)

        p_fin.markdown("⏳ **Financial Agent** — analisi costi e penali...")
        financial = analyze(orchestrator.financial_agent)
        p_fin.markdown(
            f"✅ **Financial Agent** completato — score: **{financial.get('risk_score', '?')}/10**"
        )
        progress.progress(65)

        p_prac.markdown("⏳ **Practical Agent** — analisi obblighi pratici...")
        practical = analyze(orchestrator.practical_agent)
        p_prac.markdown(
            f"✅ **Practical Agent** completato — score: **{practical.get('risk_score', '?')}/10**"
        )
        progress.progress(85)

        p_summary.markdown("⏳ **Orchestrator** — generazione executive summary...")
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

        p_summary.markdown("✅ **Executive summary** generato")
        progress.progress(100)

        st.session_state.report = report
        st.session_state.analyzing = False
        st.rerun()

    except Exception as exc:
        st.error(f"❌ Errore durante l'analisi: {exc}")
        st.markdown("Verifica le API key nel file `.env` e riprova.")
        if st.button("↩️ Torna all'upload"):
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
