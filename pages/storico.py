import streamlit as st
import pandas as pd
from modules.db_manager import get_validated_reports
from modules.data_manager import load_validated_intervention_reports

def render_storico_tab():
    """
    Renderizza la sezione "Storico" con le sottoschede per le attività
    e le relazioni validate.
    """
    st.header("Archivio Storico")

    tab1, tab2 = st.tabs(["**Storico Attività**", "**Storico Relazioni**"])

    with tab1:
        st.subheader("Archivio Report di Intervento Validati")
        df_attivita = load_validated_intervention_reports()
        if not df_attivita.empty:
            search_term = st.text_input("Cerca per PdL, descrizione o tecnico...", key="search_attivita")
            if search_term:
                df_attivita = df_attivita[
                    df_attivita["pdl"].str.contains(search_term, case=False, na=False) |
                    df_attivita["descrizione"].str.contains(search_term, case=False, na=False) |
                    df_attivita["tecnico"].str.contains(search_term, case=False, na=False)
                ]
            st.dataframe(df_attivita, use_container_width=True)
        else:
            st.success("Non ci sono report di intervento validati nell'archivio.")

    with tab2:
        st.subheader("Archivio Relazioni di Reperibilità Validate")
        df_relazioni = get_validated_reports("relazioni")
        if not df_relazioni.empty:
            display_cols = [
                "data_intervento", "tecnico_compilatore", "partner",
                "ora_inizio", "ora_fine", "corpo_relazione"
            ]
            df_display = df_relazioni[[col for col in display_cols if col in df_relazioni.columns]]
            st.dataframe(df_display, use_container_width=True)
        else:
            st.success("Non ci sono relazioni validate nell'archivio.")
