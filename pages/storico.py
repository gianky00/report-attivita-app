import streamlit as st
import pandas as pd
from modules.db_manager import (
    get_validated_reports,
    get_validated_intervention_reports,
    get_storico_richieste_materiali,
    get_storico_richieste_assenze
)

def render_storico_tab():
    """
    Renderizza la sezione "Storico" con le sottoschede per le attività
    e le relazioni validate.
    """
    st.header("Archivio Storico")

    tab1, tab2, tab3, tab4 = st.tabs([
        "**Storico Attività**",
        "**Storico Relazioni**",
        "**Storico Materiali**",
        "**Storico Assenze**"
    ])

    with tab1:
        st.subheader("Archivio Report di Intervento Validati")
        df_attivita = get_validated_intervention_reports()
        if not df_attivita.empty:
            search_term = st.text_input("Cerca per PdL, descrizione o tecnico...", key="search_attivita")
            if search_term:
                df_attivita = df_attivita[
                    df_attivita["pdl"].str.contains(search_term, case=False, na=False) |
                    df_attivita["descrizione_attivita"].str.contains(search_term, case=False, na=False) |
                    df_attivita["nome_tecnico"].str.contains(search_term, case=False, na=False)
                ]
            st.dataframe(df_attivita, use_container_width=True)
        else:
            st.success("Non ci sono report di intervento validati nell'archivio.")

    with tab2:
        st.subheader("Archivio Relazioni di Reperibilità Validate")
        df_relazioni = get_validated_reports("relazioni")
        if not df_relazioni.empty:
            # Ordina le relazioni per data di intervento
            if 'data_intervento' in df_relazioni.columns:
                df_relazioni['data_intervento'] = pd.to_datetime(df_relazioni['data_intervento'])
                df_relazioni = df_relazioni.sort_values(by="data_intervento", ascending=False)

            for _, row in df_relazioni.iterrows():
                # Formatta la data per una visualizzazione più pulita
                data_intervento_str = row['data_intervento'].strftime('%d/%m/%Y') if pd.notna(row['data_intervento']) else 'Data non disponibile'

                expander_title = f"**{data_intervento_str}** - Tecnico: **{row.get('tecnico_compilatore', 'N/D')}** - Partner: **{row.get('partner', 'N/D')}**"

                with st.expander(expander_title):
                    st.markdown(f"**Orario:** dalle {row.get('ora_inizio', 'N/D')} alle {row.get('ora_fine', 'N/D')}")
                    st.markdown("**Relazione:**")
                    # Usa una formattazione che rispetti gli a capo e il testo pre-formattato
                    st.text_area("", value=row.get('corpo_relazione', 'Nessun testo.'), height=200, disabled=True, key=f"rel_{row['id_relazione']}")
        else:
            st.success("Non ci sono relazioni validate nell'archivio.")

    with tab3:
        st.subheader("Archivio Richieste Materiali Approvate")
        df_materiali = get_storico_richieste_materiali()
        if not df_materiali.empty:
            for _, row in df_materiali.iterrows():
                timestamp_str = pd.to_datetime(row['timestamp_richiesta']).strftime('%d/%m/%Y %H:%M')
                expander_title = f"**{timestamp_str}** - Richiedente: **{row.get('nome_richiedente', 'N/D')}**"
                with st.expander(expander_title):
                    st.text_area("Dettagli Richiesta", value=row.get('dettagli_richiesta', 'Nessun dettaglio.'), height=150, disabled=True, key=f"mat_{row['id_storico']}")
        else:
            st.success("Nessuna richiesta di materiali nello storico.")

    with tab4:
        st.subheader("Archivio Richieste Assenze Approvate")
        df_assenze = get_storico_richieste_assenze()
        if not df_assenze.empty:
            for _, row in df_assenze.iterrows():
                data_inizio_str = pd.to_datetime(row['data_inizio']).strftime('%d/%m/%Y')
                data_fine_str = pd.to_datetime(row['data_fine']).strftime('%d/%m/%Y')
                expander_title = f"**{row.get('tipo_assenza', 'N/D')}** dal **{data_inizio_str}** al **{data_fine_str}** - Richiedente: **{row.get('nome_richiedente', 'N/D')}**"
                with st.expander(expander_title):
                    st.text_area("Note", value=row.get('note', 'Nessuna nota.'), height=100, disabled=True, key=f"ass_{row['id_storico']}")
        else:
            st.success("Nessuna richiesta di assenze nello storico.")
