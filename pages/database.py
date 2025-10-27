import streamlit as st
import pandas as pd
import datetime
from modules.db_manager import get_archive_filter_options, get_filtered_archived_activities, get_all_relazioni

from components.ui_components import visualizza_storico_organizzato

def render_database_tab():
    st.header("Archivio Storico")
    db_tab1, db_tab2 = st.tabs(["Ricerca Attività", "Elenco Relazioni"])

    with db_tab1:
        st.subheader("Ricerca nel Database Attività")
        filter_options = get_archive_filter_options()

        def set_date_range_15_days():
            st.session_state.db_end_date = datetime.date.today()
            st.session_state.db_start_date = st.session_state.db_end_date - datetime.timedelta(days=15)

        if 'db_start_date' not in st.session_state: st.session_state.db_start_date = None
        if 'db_end_date' not in st.session_state: st.session_state.db_end_date = None

        c1, c2, c3, c4 = st.columns(4)
        with c1: pdl_search = st.text_input("Filtra per PdL", key="db_pdl_search")
        with c2: desc_search = st.text_input("Filtra per Descrizione", key="db_desc_search")
        with c3: imp_search = st.multiselect("Filtra per Impianto", options=filter_options['impianti'], key="db_imp_search")
        with c4: tec_search = st.multiselect("Filtra per Tecnico/i", options=filter_options['tecnici'], key="db_tec_search")

        st.divider()
        st.markdown("##### Filtra per Data Intervento")
        d1, d2, d3, d4 = st.columns([1,1,1,2])
        with d1: st.date_input("Da:", key="db_start_date", format="DD/MM/YYYY")
        with d2: st.date_input("A:", key="db_end_date", format="DD/MM/YYYY")
        with d3: st.button("Ultimi 15 gg", key="db_last_15_days", on_click=set_date_range_15_days)

        interventi_eseguiti_only = st.checkbox("Mostra solo interventi eseguiti", value=True, key="db_show_executed")
        st.divider()
        st.info("""**Nota:** Per impostazione predefinita, vengono visualizzate le 40 attività più recenti. Usa i filtri per una ricerca più specifica o il pulsante "Carica Altri" per visualizzare più risultati.""")

        # --- Logica Paginazione e Filtri Unificata ---
        if 'db_page' not in st.session_state:
            st.session_state.db_page = 0

        current_db_filters = (
            pdl_search, desc_search, tuple(sorted(imp_search)),
            tuple(sorted(tec_search)), interventi_eseguiti_only,
            st.session_state.db_start_date, st.session_state.db_end_date
        )

        if st.session_state.get('last_db_filters') != current_db_filters:
            st.session_state.db_page = 0
            st.session_state.last_db_filters = current_db_filters

        with st.spinner("Ricerca in corso nel database..."):
            risultati_df = get_filtered_archived_activities(
                pdl_search, desc_search, imp_search, tec_search,
                interventi_eseguiti_only, st.session_state.db_start_date,
                st.session_state.db_end_date
            )

        if risultati_df.empty:
            st.info("Nessun record trovato.")
        else:
            ITEMS_PER_PAGE = 40
            total_results = len(risultati_df)

            end_idx = (st.session_state.db_page + 1) * ITEMS_PER_PAGE
            items_to_display_df = risultati_df.iloc[0:end_idx]

            search_is_active = any(current_db_filters[:-2]) or all(current_db_filters[-2:])
            if search_is_active:
                st.info(f"Trovati {total_results} risultati. Visualizzati {len(items_to_display_df)}.")
            else:
                st.info(f"Visualizzati {len(items_to_display_df)} dei {total_results} interventi più recenti.")

            for index, row in items_to_display_df.iterrows():
                pdl = row['PdL']
                impianto = row.get('IMP', 'N/D')
                descrizione = row.get('DESCRIZIONE_ATTIVITA', 'N/D')
                storico = row.get('Storico', [])

                expander_label = f"PdL {pdl} | {impianto} | {str(descrizione)[:60]}..."
                with st.expander(expander_label):
                    visualizza_storico_organizzato(storico, pdl)

            if end_idx < total_results:
                st.divider()
                if st.button("Carica Altri", key="db_load_more"):
                    st.session_state.db_page += 1
                    st.rerun()

    with db_tab2:
        st.subheader("Elenco Completo Relazioni Inviate")
        relazioni_df = get_all_relazioni()
        if relazioni_df.empty:
            st.info("Nessuna relazione trovata nel database.")
        else:
            relazioni_df['data_intervento'] = pd.to_datetime(relazioni_df['data_intervento']).dt.strftime('%d/%m/%Y')
            relazioni_df['timestamp_invio'] = pd.to_datetime(relazioni_df['timestamp_invio']).dt.strftime('%d/%m/%Y %H:%M')
            st.dataframe(relazioni_df, width='stretch')
