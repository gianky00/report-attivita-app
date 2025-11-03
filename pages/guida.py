import streamlit as st

def render_guida_tab(ruolo):
    st.title("❓ Guida all'Uso del Gestionale")
    st.write("Benvenuto nel Gestionale. Questa guida fornisce una panoramica completa delle funzionalità dell'applicazione, con sezioni dedicate sia ai **Tecnici** che agli **Amministratori**.")
    st.info("Utilizza i menù a tendina sottostanti per esplorare le diverse sezioni e scoprire come utilizzare al meglio ogni strumento a tua disposizione.")

    with st.expander("📝 Attività Assegnate", expanded=True):
        st.markdown("""
        Questa sezione è il fulcro del tuo lavoro quotidiano. Qui puoi visualizzare e rendicontare le attività a te assegnate.

        - **Attività di Oggi:** Contiene l'elenco delle attività programmate per la giornata corrente.
        - **Recupero Attività:** Mostra le attività non rendicontate degli ultimi 30 giorni.
        - **Attività Validate:** Un archivio di sola lettura dei tuoi report già approvati.
        - **Compila Relazione:** Uno strumento per la stesura di relazioni dettagliate (es. interventi di reperibilità), con il supporto dell'IA per la correzione e il miglioramento del testo.

        **Come compilare un report:**
        Per ogni attività, puoi compilare un report dettagliato. Se un'attività è assegnata a un team, solo i **Tecnici** possono compilare il report.
        """)

    with st.expander("📅 Gestione Turni"):
        st.markdown("""
        Questa sezione ti permette di gestire la tua disponibilità per i turni di assistenza, straordinario e reperibilità.

        - **Turni:** Visualizza i turni disponibili e prenota la tua partecipazione.
        - **Bacheca:** Un'area dove i colleghi pubblicano i turni che non possono coprire. Il primo che accetta il turno lo prende in carico.
        - **Sostituzioni:** Puoi richiedere una sostituzione a un collega specifico o rispondere a una richiesta ricevuta.

        **Gestione della Reperibilità:**
        Il calendario settimanale mostra i tuoi turni di reperibilità. Se non puoi coprire un turno, puoi pubblicarlo in bacheca per renderlo disponibile ad altri.
        """)

    with st.expander("📋 Richieste"):
        st.markdown("""
        Utilizza questa sezione per inviare richieste formali di materiali o assenze.

        - **Richiesta Materiali:** Invia una richiesta per materiali di consumo o attrezzature.
        - **Richiesta Assenze:** Invia richieste di ferie o permessi. Lo storico delle richieste di assenza è visibile solo agli **Amministratori**.
        """)

    with st.expander("🗂️ Archivio Storico"):
        st.markdown("""
        L'**Archivio Storico** è la memoria a lungo termine dell'applicazione. Qui puoi consultare tutti i report, le relazioni e le richieste che sono state validate e archiviate. La sezione è suddivisa in quattro aree tematiche per facilitare la ricerca.

        #### Storico Attività
        Questa scheda contiene l'archivio completo di tutti i **report di intervento** che sono stati validati.
        - **Ricerca Rapida:** Utilizza la barra di ricerca per filtrare istantaneamente i report per **PdL, descrizione dell'attività o nome del tecnico**.
        - **Visualizzazione Organizzata:** I risultati sono raggruppati per **PdL (Punto di Lavoro)**. Ogni gruppo può essere espanso per visualizzare i singoli interventi in ordine cronologico.

        #### Storico Relazioni
        Qui trovi tutte le **relazioni di reperibilità** che sono state approvate. Le relazioni sono ordinate dalla più recente alla meno recente e possono essere espanse per leggere il contenuto completo.

        #### Storico Materiali
        Questa scheda elenca tutte le **richieste di materiali** che sono state inviate e approvate. Ogni richiesta è presentata in una scheda espandibile che mostra i dettagli, la data e il richiedente.

        #### Storico Assenze
        In quest'area puoi consultare lo storico di tutte le **richieste di ferie e permessi** approvate. Come per i materiali, ogni richiesta è visualizzabile in dettaglio espandendo la relativa scheda.
        """)

    if ruolo == "Amministratore":
        with st.expander("⚙️ Amministrazione (Solo Amministratori)"):
            st.markdown("""
            Questa sezione contiene strumenti avanzati per la gestione del sistema e del team.

            #### Caposquadra
            - **Performance Team:** Analizza le metriche di performance dei tecnici.
            - **Crea Nuovo Turno:** Crea e pubblica nuovi turni di assistenza o straordinario.
            - **Gestione Dati:** Funzionalità avanzate per la gestione del database e la sincronizzazione manuale con file esterni.
            - **Validazione Report:** Revisiona, modifica e approva i report e le relazioni inviate dai tecnici.

            #### Sistema
            - **Gestione Account:** Crea nuovi utenti, modifica i loro ruoli e resetta le password o le configurazioni 2FA.
            - **Cronologia Accessi:** Monitora tutti i tentativi di accesso al sistema, riusciti e non.
            - **Gestione IA:** Strumenti per la revisione e l'addestramento del modello di intelligenza artificiale utilizzato per la stesura dei report.
            """)

    with st.expander("🔐 Sicurezza dell'Account"):
        st.markdown("""
        **Verifica in Due Passaggi (2FA):**
        Al primo accesso, ti verrà richiesto di configurare la 2FA per garantire la sicurezza del tuo account. Se perdi l'accesso al tuo dispositivo, contatta un amministratore per resettare la configurazione.
        """)
