import streamlit as st

def render_guida_tab(ruolo):
    st.title("❓ Guida all'Uso del Gestionale")
    st.write("Benvenuto! Questa guida ti aiuterà a usare al meglio tutte le funzionalità dell'applicazione. Se hai dubbi, questo è il posto giusto per trovare risposte.")
    st.info("Usa i menù a tendina qui sotto per esplorare le diverse sezioni. La tua sessione di lavoro rimane attiva anche se aggiorni la pagina!")

    # Sezione 1: Il Lavoro Quotidiano
    with st.expander("📝 IL TUO LAVORO QUOTIDIANO: Attività e Report", expanded=True):
        st.markdown("""
        Questa è la sezione principale per la gestione delle tue attività. È il tuo punto di partenza ogni giorno.

        #### Sottosezioni Principali:
        - **Attività di Oggi**: Qui trovi l'elenco delle attività programmate per te nella giornata corrente.
        - **Recupero Attività**: Mostra le attività dei 7 giorni precedenti che non hai ancora rendicontato. È un promemoria per non lasciare indietro nulla.

        #### Come Compilare un Report:
        Per ogni attività, vedrai il **codice PdL**, la **descrizione** e lo **storico** degli interventi passati. Per rendicontare, hai due opzioni:
        1.  **✍️ Report Guidato (IA)**: Il sistema ti fa delle domande per aiutarti a scrivere un report completo e standardizzato. È l'opzione consigliata.
        2.  **📝 Report Manuale**: Un campo di testo libero dove puoi scrivere il report come preferisci.

        > **Nota per i Team**: Se un'attività è assegnata a un team, solo i membri con ruolo **Tecnico** possono compilare e inviare il report. Gli **Aiutanti** possono consultare l'attività ma non compilarla.

        #### Compilare una Relazione (es. Reperibilità):
        Se sei **Tecnico** o **Amministratore**, hai una terza sottosezione per scrivere relazioni più complesse, come quelle di reperibilità.
        - **Compila i campi**: Inserisci data, orari e l'eventuale collega con cui hai lavorato.
        - **Scrivi la relazione**: Descrivi l'intervento nel dettaglio.
        - **Usa l'IA per migliorare**: Clicca su **"Correggi con IA"** per ricevere una versione del testo migliorata, più chiara e professionale. Puoi scegliere di usare il testo suggerito o mantenere il tuo.
        """)

    # Sezione 2: Pianificazione e Visione d'Insieme
    with st.expander("📊 PIANIFICAZIONE E CONTROLLO: Visione d'Insieme", expanded=False):
        st.markdown("""
        Questa sezione ti offre una visione più ampia su tutte le attività, non solo le tue. È divisa in due aree:

        #### 1. Controllo
        - **Obiettivo**: Avere un quadro generale dello stato di avanzamento di **tutte le attività** programmate.
        - **Cosa Mostra**: Grafici e metriche che riassumono le attività per area e stato (es. terminate, in corso). È utile per capire a colpo d'occhio come sta procedendo il lavoro.
        - **Come si usa**: Filtra per **Area** per concentrarti su zone specifiche. Gli stati "Scaduto" e "Da Chiudere" sono raggruppati in "Terminata" per semplicità.

        #### 2. Pianificazione
        - **Obiettivo**: Consultare il **dettaglio di ogni singola attività** programmata, anche quelle non assegnate a te.
        - **Cosa Mostra**: Una lista di "card", una per ogni attività, con tutti i dettagli (PdL, descrizione, giorni programmati) e lo storico degli interventi passati.
        - **Come si usa**: Usa i filtri per cercare per **PdL, Area o Giorno** della settimana. Il grafico del carico di lavoro ti mostra quante attività sono previste ogni giorno per ciascuna area.
        """)

    # Sezione 3: Database
    with st.expander("🗂️ DATABASE: Ricerca Storica", expanded=False):
        st.subheader("Come Trovare Interventi Passati")
        st.markdown("""
        La sezione **Database** è il tuo archivio storico completo. Usala per trovare qualsiasi intervento che sia stato registrato nel sistema.

        Puoi cercare usando una combinazione di filtri:
        - **PdL**: Cerca un Punto di Lavoro specifico.
        - **Descrizione**: Cerca parole chiave nella descrizione dell'attività (es. "controllo", "pompa").
        - **Impianto**: Filtra per uno o più impianti specifici.
        - **Tecnico/i**: Seleziona uno o più tecnici per vedere solo i loro interventi.
        - **Filtro per Data**:
            - **Da / A**: Imposta un intervallo di date preciso per la tua ricerca.
            - **Ultimi 15 gg**: Clicca questo comodo pulsante per vedere tutti gli interventi degli ultimi 15 giorni.

        > **Importante**: Per impostazione predefinita, la ricerca mostra solo gli **interventi eseguiti**, cioè quelli per cui è stato compilato un report. Se vuoi vedere anche le **attività pianificate** che non hanno ancora un report, deseleziona la casella "Mostra solo interventi eseguiti".
        """)

    # Sezione 4: Gestione Turni
    with st.expander("📅 GESTIONE TURNI: Assistenza, Straordinari e Reperibilità", expanded=False):
        st.markdown("""
        Qui puoi gestire la tua partecipazione ai vari tipi di turno.

        #### Turni di Assistenza e Straordinario
        - **Prenotazione**: Trova un turno con posti liberi (indicato da ✅), scegli il tuo ruolo (Tecnico o Aiutante) e clicca "Conferma Prenotazione".
        - **Cedere un turno**: Se non puoi più partecipare, hai 3 opzioni:
            1.  **Cancella Prenotazione**: La tua prenotazione viene rimossa e il posto torna libero per tutti.
            2.  **📢 Pubblica in Bacheca**: Rendi il tuo posto disponibile a tutti i colleghi. Il primo che lo accetta prenderà il tuo turno automaticamente.
            3.  **🔄 Chiedi Sostituzione**: Chiedi a un collega specifico di sostituirti.

        #### Turni di Reperibilità
        - **Visualizzazione**: Il calendario ti mostra i tuoi turni di reperibilità assegnati.
        - **Cedere un turno**: Se sei di turno e non puoi coprirlo, clicca su **"Gestisci"** e poi **"Pubblica in Bacheca"** per renderlo disponibile ad altri.

        #### La Bacheca
        Nella sezione **📢 Bacheca** trovi tutti i turni (di qualsiasi tipo) che i colleghi hanno messo a disposizione. Il primo che clicca su "Prendi questo turno" lo ottiene.
        """)

    # Sezione 5: Richieste
    with st.expander("📋 RICHIESTE: Materiali e Assenze", expanded=False):
        st.markdown("""
        Usa questa sezione per inviare richieste formali.
        - **Richiesta Materiali**: Compila il modulo per richiedere materiali di consumo o attrezzature. Le richieste sono visibili a tutti per trasparenza.
        - **Richiesta Assenze**: Invia richieste di ferie o permessi. Solo gli amministratori possono vedere lo storico di queste richieste.
        """)

    # Sezione 6: Sicurezza
    with st.expander("🔐 SICUREZZA: Gestione Account e 2FA", expanded=False):
        st.subheader("Impostare la Verifica in Due Passaggi (2FA)")
        st.markdown("""
        Per la sicurezza del tuo account, al primo accesso ti verrà chiesto di configurare la verifica in due passaggi (2FA).
        1.  **Installa un'app di Autenticazione** sul tuo cellulare (es. Google Authenticator, Microsoft Authenticator).
        2.  **Scansiona il QR Code** che appare sullo schermo con la tua app.
        3.  **Inserisci il codice** a 6 cifre generato dall'app per completare la configurazione.

        D'ora in poi, per accedere dovrai inserire la tua password e il codice temporaneo dalla tua app.
        """)
        st.subheader("Cosa fare se cambi cellulare?")
        st.warning("Se cambi cellulare o perdi accesso alla tua app, **contatta un amministratore**. Potrà resettare la tua configurazione 2FA e permetterti di registrarla sul nuovo dispositivo.")

    # Sezione 7: Admin
    if ruolo == "Amministratore":
        with st.expander("👑 FUNZIONALITÀ AMMINISTRATORE", expanded=False):
            st.subheader("Pannello di Controllo per Amministratori")
            st.markdown("""
            Questa sezione, visibile solo a te, contiene strumenti avanzati per la gestione del team e del sistema.

            #### Dashboard Caposquadra (Gestione Operativa)
            - **Performance Team**: Analizza le metriche di performance dei tecnici in un dato intervallo di tempo. Seleziona un periodo e clicca "Calcola Performance". Se non ci sono dati, il sistema ti avviserà con un messaggio.
            - **Crea Nuovo Turno**: Crea nuovi turni di assistenza o straordinario.
            - **Gestione Dati**: Sincronizza i dati tra il file Excel di pianificazione e il database dell'app.
            - **Validazione Report**: Revisiona, modifica e approva i report inviati dai tecnici.

            #### Dashboard Tecnica (Configurazione di Sistema)
            - **Gestione Account**: Crea nuovi utenti, modifica ruoli e resetta password o 2FA.
            - **Cronologia Accessi**: Monitora tutti i tentativi di accesso al sistema.
            - **Gestione IA**: Addestra e migliora il modello di IA che assiste nella stesura dei report.
            """)
