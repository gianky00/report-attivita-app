import streamlit as st

from modules.utils import render_svg_icon


def render_guida_tab(ruolo: str) -> None:
    """Renderizza la sezione Guida dell'applicazione aggiornata per Horizon."""
    st.title("Horizon Guide")
    st.write(
        "Benvenuto su Horizon, la piattaforma avanzata per la gestione delle operazioni tecniche. "
        "Questa guida fornisce istruzioni dettagliate sull'uso delle funzionalità di sicurezza, gestione dati e rendicontazione."
    )

    st.info(
        "Esplora i moduli sottostanti per comprendere come gestire il tuo profilo, rendicontare le attività "
        "e monitorare lo stato del sistema."
    )

    # --- SEZIONE PROFILO ---
    with st.expander("Profilo e Impostazioni", expanded=True):
        st.markdown(
            f"{render_svg_icon('user', 24)} **Gestione Account Personale**", unsafe_allow_html=True
        )
        st.markdown("""
        Attraverso il menu **'Impostazioni'** nella sidebar, puoi gestire la tua identità digitale:

        - **Profilo:** Visualizza i tuoi dati anagrafici, il ruolo assegnato e la matricola.
        - **Password:** Cambia autonomamente la tua password di accesso.
        - **Sicurezza (2FA):** Attiva o disattiva la protezione con codice temporaneo (OTP).
        """)

    # --- SEZIONE ATTIVITÀ ---
    with st.expander("Attività e Rendicontazione"):
        st.markdown(
            f"{render_svg_icon('report', 24)} **Rendicontazione Operativa**", unsafe_allow_html=True
        )
        st.markdown("""
        Gestione del flusso di lavoro giornaliero con dati sincronizzati:

        - **Attività di Oggi:** Elenco degli interventi assegnati per la data corrente.
        - **Recupero Attività:** Visualizza e compila report per attività degli ultimi 30 giorni.
        - **Compila Relazione:** Supporto IA per la stesura di testi tecnici professionali.
        """)

    # --- SEZIONE TURNI ---
    with st.expander("Gestione Turni e Reperibilità"):
        st.markdown(
            f"{render_svg_icon('calendar', 24)} **Turni e Disponibilità**", unsafe_allow_html=True
        )
        st.markdown("""
        Pianificazione operativa del team:

        - **Turni Assistenza:** Prenotazione per turni extra e straordinari.
        - **Bacheca Scambi:** Gestione autonoma delle sostituzioni in reperibilità.
        - **Reperibilità:** Calendario dinamico della rotazione ufficiale.
        """)

    # --- SEZIONE RICHIESTE ---
    with st.expander("Richieste Materiali e Assenze"):
        st.markdown(
            f"{render_svg_icon('request', 24)} **Modulistica Digitale**", unsafe_allow_html=True
        )
        st.markdown("""
        Invio richieste formali:
        - **Materiali:** Richiesta componenti per PdL specifici.
        - **Assenze:** Richieste di Ferie o Permessi direttamente all'amministrazione.
        """)

    # --- SEZIONE AMMINISTRAZIONE ---
    if ruolo == "Amministratore":
        with st.expander("Strumenti Amministrativi"):
            st.markdown(
                f"{render_svg_icon('settings', 24)} **Area Sistema e Caposquadra**",
                unsafe_allow_html=True,
            )
            st.markdown("""
            Funzionalità riservate:

            - **Validazione:** Approvazione finale di report e relazioni.
            - **Gestione Dati:** Manutenzione diretta del database SQLite.
            - **Stato Sistema:** Diagnostica dei percorsi di rete e mount Docker.
            - **Cronologia Accessi:** Audit log dei tentativi di login.
            """)

    from constants import APP_VERSION, VERSION_DATE

    # --- SEZIONE NOVITÀ ---
    with st.expander("Novità e Aggiornamenti", expanded=False):
        from modules.changelog import render_changelog_ui

        st.markdown(
            f"{render_svg_icon('bulletin', 24)} **Cosa c'è di nuovo**", unsafe_allow_html=True
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
