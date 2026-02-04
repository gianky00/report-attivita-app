import streamlit as st


def render_guida_tab(ruolo):
    st.title("❓ Guida all'Uso del Gestionale")
    st.write(
        "Benvenuto nel Gestionale. Questa guida fornisce una panoramica completa "
        "delle funzionalità dell'applicazione, con sezioni dedicate sia ai "
        "**Tecnici** che agli **Amministratori**."
    )
    st.info(
        "Utilizza i menù a tendina sottostanti per esplorare le diverse sezioni "
        "e scoprire come utilizzare al meglio ogni strumento a tua disposizione."
    )

    with st.expander("📝 Attività Assegnate", expanded=True):
        st.markdown("""
        Questa sezione è il fulcro del tuo lavoro quotidiano. Qui puoi
        visualizzare e rendicontare le attività a te assegnate.

        - **Attività di Oggi:** Elenco delle attività per la giornata corrente.
        - **Recupero Attività:** Attività non rendicontate degli ultimi 30 giorni.
        - **Attività Validate:** Archivio di sola lettura dei report approvati.
        - **Compila Relazione:** Strumento per la stesura di relazioni dettagliate
          con il supporto dell'IA per la correzione.

        **Come compilare un report:**
        Per ogni attività, puoi compilare un report dettagliato.
        Se un'attività è assegnata a un team, solo i **Tecnici** possono
        compilare il report.
        """)

    with st.expander("📅 Gestione Turni"):
        st.markdown("""
        Questa sezione ti permette di gestire la tua disponibilità per i turni
        di assistenza, straordinario e reperibilità.

        - **Turni:** Visualizza i turni disponibili e prenota la partecipazione.
        - **Bacheca:** Area dove i colleghi pubblicano i turni liberi.
        - **Sostituzioni:** Richiedi una sostituzione a un collega specifico.

        **Gestione della Reperibilità:**
        Il calendario settimanale mostra i tuoi turni di reperibilità.
        Se non puoi coprire un turno, puoi pubblicarlo in bacheca.
        """)

    with st.expander("📋 Richieste"):
        st.markdown("""
        Utilizza questa sezione per inviare richieste formali di materiali
        o assenze.

        - **Richiesta Materiali:** Richiesta per materiali o attrezzature.
        - **Richiesta Assenze:** Richieste di ferie o permessi.
          Lo storico è visibile solo agli **Amministratori**.
        """)

    with st.expander("🗂️ Archivio Storico"):
        st.markdown("""
        L'**Archivio Storico** è la memoria a lungo termine dell'applicazione.
        Qui puoi consultare tutti i report, le relazioni e le richieste validate.

        #### Storico Attività
        Contiene l'archivio completo di tutti i **report di intervento** validati.
        - **Ricerca Rapida:** Filtra per **PdL, descrizione o tecnico**.
        - **Organizzazione:** I risultati sono raggruppati per **PdL**.

        #### Storico Relazioni
        Qui trovi tutte le **relazioni di reperibilità** approvate,
        ordinate dalla più recente.

        #### Storico Materiali
        Elenca tutte le **richieste di materiali** inviate e approvate.

        #### Storico Assenze
        Storico di tutte le **richieste di ferie e permessi** approvate.
        """)

    if ruolo == "Amministratore":
        with st.expander("⚙️ Amministrazione (Solo Amministratori)"):
            st.markdown("""
            Strumenti avanzati per la gestione del sistema e del team.

            #### Caposquadra
            - **Performance Team:** Analizza le metriche dei tecnici.
            - **Crea Nuovo Turno:** Crea turni di assistenza o straordinario.
            - **Gestione Dati:** Gestione DB e sincronizzazione manuale.
            - **Validazione Report:** Revisiona e approva i report.

            #### Sistema
            - **Gestione Account:** Crea utenti, ruoli e resetta password/2FA.
            - **Cronologia Accessi:** Monitora i tentativi di accesso.
            - **Gestione IA:** Strumenti per la revisione e addestramento dell'IA.
            """)

    with st.expander("🔐 Sicurezza dell'Account"):
        st.markdown("""
        **Verifica in Due Passaggi (2FA):**
        Al primo accesso, configura la 2FA per la sicurezza dell'account.
        Se perdi l'accesso, contatta un amministratore.
        """)
