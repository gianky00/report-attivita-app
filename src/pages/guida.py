import streamlit as st

from modules.utils import render_svg_icon


def render_guida_tab(ruolo: str) -> None:
    """Renderizza la sezione Guida dell'applicazione aggiornata per Horizon."""
    
    st.info(
        "Benvenuto su **Horizon**. Questa guida fornisce le istruzioni operative per l'utilizzo del sistema."
    )

    # --- SEZIONE 1: RUOLI E ACCESSO ---
    with st.expander("🔑 Accesso e Ruoli Utente", expanded=True):
        st.markdown(f"{render_svg_icon('user', 24)} **Il tuo profilo**", unsafe_allow_html=True)
        st.write("""
        L'accesso a Horizon avviene tramite **Matricola** e **Password**.
        
        **Differenza tra i Ruoli:**
        *   **Tecnico:** Responsabile primario degli interventi. Ha accesso completo alla rendicontazione e alla gestione turni.
        *   **Aiutante:** Membro del team di supporto. È pienamente abilitato a compilare report tecnici e relazioni di reperibilità esattamente come il tecnico.
        *   **Amministratore:** Gestisce gli account e valida i report finali.
        
        **Sicurezza Avanzata (2FA):** 
        Puoi attivare l'Autenticazione a due fattori (2FA) nella pagina **Impostazioni**. Questo aggiunge un codice temporaneo (OTP) generato sul tuo smartphone per rendere l'account inviolabile.
        """)

    # --- SEZIONE 2: GESTIONE ATTIVITÀ ---
    with st.expander("📋 Rendicontazione e PdL (Permessi di Lavoro)"):
        st.markdown(f"{render_svg_icon('report', 24)} **Il Ciclo di Vita di un Intervento**", unsafe_allow_html=True)
        st.write("""
        Horizon sincronizza automaticamente i dati dai server di rete ogni 5 minuti. La sincronizzazione avviene in background tramite un servizio dedicato, garantendo dati sempre freschi senza rallentare l'app.
        
        **Le fasi di un'attività:**
        1.  **PIANIFICATO:** L'intervento appare nella tua scheda 'Attività di Oggi' (estratto dai Permessi di Lavoro Excel).
        2.  **INVIATO:** Hai compilato e salvato il report. L'attività scompare da quelle 'da fare' e si sposta in 'Attività Inviate'. In questa fase puoi ancora modificarla se noti errori.
        3.  **VALIDATO:** Un responsabile ha approvato il tuo report. L'attività è definitiva.
        
        **Sottoschede principali:**
        *   **Attività di Oggi:** Gli interventi che devi svolgere nel turno corrente.
        *   **Recupero Attività:** Permette di rendicontare interventi dimenticati o non svolti negli ultimi 30 giorni.
        *   **Attività Validate:** Qui puoi consultare i tuoi report che sono già stati approvati dall'amministrazione.
        *   **Compilazione AI:** Quando scrivi un report, puoi usare l'IA (Gemini) per revisionare il testo o verificare la sigla degli strumenti secondo lo standard **ISA S5.1**.
        *   **Esclusione:** Se un'attività non ti compete, puoi usare il tasto 'Escludi' per nasconderla permanentemente.
        """)

    # --- SEZIONE 3: TURNI E REPERIBILITÀ ---
    with st.expander("📅 Turni, Reperibilità e Bacheca Scambi"):
        st.markdown(f"{render_svg_icon('calendar', 24)} **Pianificazione Team**", unsafe_allow_html=True)
        st.write("""
        Horizon gestisce la rotazione del personale in modo dinamico.
        
        **Turni Assistenza:**
        Visualizza i turni extra creati dall'amministrazione e prenotati come Tecnico o Aiutante. Il sistema ti avviserà se ci sono conflitti con i tuoi turni di reperibilità esistenti.
        
        **Bacheca Scambi (Market):**
        Se hai un impegno e non puoi coprire un turno di reperibilità già assegnato:
        1.  Vai in 'Gestione Turni' -> 'I Miei Turni'.
        2.  Clicca su **'Metti in Bacheca'**. Il turno diventerà visibile a tutti i colleghi.
        3.  Un altro collega potrà 'Prendere il turno' dalla Bacheca, e il sistema effettuerà il subentro automatico.
        
        **Calendario Reperibilità:**
        Visualizzazione della rotazione ufficiale programmata. Nota: le date nei calendari devono essere sempre inserite nel formato **GG/MM/AAAA**.
        """)

    # --- SEZIONE 4: RELAZIONI E RICHIESTE ---
    with st.expander("📝 Relazioni di Fine Turno e Materiali"):
        st.markdown(f"{render_svg_icon('request', 24)} **Modulistica e Comunicazione**", unsafe_allow_html=True)
        st.write("""
        **Relazione di Reperibilità:**
        Al termine del tuo turno di reperibilità, compila la Relazione Generale nella tab 'Compila Relazione'. 
        Indica il partner, gli orari precisi di intervento e un riepilogo strutturato. Questo documento è fondamentale per la rendicontazione verso il cliente.
        
        **Richieste Materiali:**
        Se durante un intervento rilevi la necessità di componenti (valvole, sensori, ecc.), usa il modulo 'Richieste'.
        *   Seleziona il PdL di riferimento.
        *   Descrivi il materiale necessario.
        """)

    # --- SEZIONE 5: RICERCA E STORICO ---
    with st.expander("🔍 Programmazione e Storico Interventi"):
        st.markdown(f"{render_svg_icon('archive', 24)} **Consultazione Dati**", unsafe_allow_html=True)
        st.write("""
        *   **Programmazione PDL:** Mostra la pianificazione di oggi e della settimana. Usa la barra di ricerca per filtrare istantaneamente per **Codice PDL**, **Nome Team** o **Descrizione attività**.
        *   **Storico:** Accedi all'archivio di tutti i report e le relazioni validate. Puoi cercare interventi passati per capire la cronologia delle manutenzioni su un determinato impianto.
        """)

    # --- SEZIONE 6: NOTIFICHE E SISTEMA ---
    with st.expander("🔔 Notifiche e Stato"):
        st.markdown(f"{render_svg_icon('info', 24)} **Rimanere Informati**", unsafe_allow_html=True)
        st.write("""
        **Centro Notifiche:**
        In alto a destra (icona campanella) trovi gli avvisi personalizzati: validazioni, nuovi turni disponibili o messaggi amministrativi.
        
        **Stato Connessione:**
        Horizon monitora costantemente il database e i percorsi di rete. In caso di problemi tecnici o server non raggiungibili, apparirà automaticamente un **avviso di errore nella sidebar** per informarti che alcune funzioni potrebbero essere limitate.
        """)

    # --- SEZIONE AMMINISTRAZIONE ---
    if ruolo == "Amministratore":
        with st.expander("🛠️ Area Amministratore (Riservato)"):
            st.markdown(
                f"{render_svg_icon('settings', 24)} **Controllo Totale**",
                unsafe_allow_html=True,
            )
            st.markdown("""
            L'area Amministratore permette di mantenere l'integrità del sistema:
            *   **Gestione Account:** Crea utenti, resetta credenziali e **disabilita account** (il logout sarà forzato immediatamente).
            *   **Validazione:** Approva i report inviati rendendoli definitivi nello storico.
            *   **Gestione Dati:** Importa/Esporta tabelle e pulisci i log.
            *   **Stato Sistema:** Diagnostica tecnica dei percorsi di rete e dei mount Docker.
            """)

    from constants import APP_VERSION, VERSION_DATE

    # --- SEZIONE NOVITÀ ---
    with st.expander("🚀 Novità Horizon v" + APP_VERSION, expanded=False):
        from modules.changelog import render_changelog_ui

        st.markdown(
            f"{render_svg_icon('bulletin', 24)} **Ultimi Aggiornamenti**", unsafe_allow_html=True
        )
        render_changelog_ui()

    st.divider()
    footer_html = f"""
    <div style='display: flex; align-items: center; gap: 10px; color: gray;'>
        {render_svg_icon("info", 16)}
        <span>Horizon Platform v{APP_VERSION} ({VERSION_DATE}) - Technical Operations Hub</span>
    </div>
    """
    st.markdown(footer_html, unsafe_allow_html=True)
