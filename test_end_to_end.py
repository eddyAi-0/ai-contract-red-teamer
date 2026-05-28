import json
from orchestrator.orchestrator import Orchestrator
from rag.vectorstore import VectorStore

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


def run_analysis():
    print("=" * 70)
    print("AI CONTRACT RED-TEAMER — Test end-to-end")
    print("=" * 70)

    try:
        vs = VectorStore()
        if vs.is_indexed():
            print("\n[OK] RAG attivo (GDPR indicizzato)")
        else:
            print("\n[WARN] RAG vuoto — lancia 'python -m rag.indexer' prima")
            vs = None
    except Exception as e:
        print(f"\n[WARN] RAG non disponibile: {e}")
        vs = None

    print("\nInizializzazione agenti...")
    orchestrator = Orchestrator(vectorstore=vs)

    print("\nAnalisi del contratto in corso (30-60 secondi)...")
    report = orchestrator.analyze(CONTRATTO_ESEMPIO)

    print("\n" + "=" * 70)
    print("REPORT FINALE")
    print("=" * 70)

    print(f"\nOVERALL RISK SCORE: {report['overall_risk_score']}/10  "
          f"[{report['risk_label']}]")
    print(f"Problemi totali: {report['findings_count']}")

    print("\n--- Score per agente ---")
    for agent, score in report['agent_scores'].items():
        print(f"  - {agent.upper()}: {score}/10")

    print("\n--- EXECUTIVE SUMMARY ---")
    print(report['executive_summary'])

    print("\n--- FINDINGS (ordinati per gravita') ---")
    for i, f in enumerate(report['total_findings'], 1):
        print(f"\n{i}. [{f.get('severity', 'low').upper()}] "
              f"({f.get('source_agent', '?')}) {f.get('title', 'N/A')}")
        print(f"   Descrizione: {f.get('description', '')[:200]}")
        if f.get('clause_reference'):
            print(f"   Clausola: \"{f['clause_reference'][:150]}\"")
        print(f"   Raccomandazione: {f.get('recommendation', 'N/A')[:200]}")
        if f.get('legal_citations'):
            print(f"   Fonti citate:")
            for cit in f['legal_citations']:
                print(f"      - {cit.get('source', '?')}: "
                      f"\"{cit.get('excerpt', '')[:120]}\"")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    run_analysis()
