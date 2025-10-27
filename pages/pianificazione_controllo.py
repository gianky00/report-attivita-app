import streamlit as st
import pandas as pd
from modules.data_manager import carica_dati_attivita_programmate

from components.ui_components import visualizza_storico_organizzato


def render_situazione_impianti_tab():
    st.header("Controllo Generale Attività")
    st.info("Questa sezione fornisce una visione aggregata dello stato di avanzamento di tutte le attività programmate.")

    df = carica_dati_attivita_programmate()

    if df.empty:
        st.warning("Nessun dato sulle attività programmate trovato nel database.")
        return

    # Raggruppa gli stati "DA CHIUDERE" e "SCADUTO" in "TERMINATA"
    df['STATO_PdL'] = df['STATO_PdL'].replace(['DA CHIUDERE', 'SCADUTO'], 'TERMINATA')


    # --- Filtri ---
    st.subheader("Filtra Dati")

    # Ora c'è solo un filtro per Area
    aree_disponibili = sorted(df['AREA'].dropna().unique()) if 'AREA' in df.columns else []
    default_aree = aree_disponibili
    aree_selezionate = st.multiselect("Filtra per Area", options=aree_disponibili, default=default_aree, key="area_filter_situazione")

    # Applica filtro per area
    filtered_df = df.copy()
    if aree_selezionate:
        filtered_df = filtered_df[filtered_df['AREA'].isin(aree_selezionate)]

    st.divider()

    if filtered_df.empty:
        st.info("Nessuna attività corrisponde ai filtri selezionati.")
        return

    # --- Metriche ---
    st.subheader("Metriche di Riepilogo")
    total_activities = len(filtered_df)
    # La metrica delle completate ora conta solo 'TERMINATA'
    completed_activities = len(filtered_df[filtered_df['STATO_PdL'] == "TERMINATA"])
    pending_activities = total_activities - completed_activities

    c1, c2, c3 = st.columns(3)
    c1.metric("Totale Attività", total_activities)
    c2.metric("Attività Terminate", completed_activities) # Etichetta cambiata
    c3.metric("Attività da Completare", pending_activities)

    # --- Grafici ---
    st.subheader("Visualizzazione Dati")

    st.markdown("#### Attività per Area e Stato")
    if 'AREA' in filtered_df.columns and 'STATO_PdL' in filtered_df.columns:
        # Crea un pivot table per avere il conteggio per Area e Stato
        status_pivot = filtered_df.groupby(['AREA', 'STATO_PdL']).size().unstack(fill_value=0)

        # Assicurati che le colonne desiderate esistano
        if 'TERMINATA' not in status_pivot.columns:
            status_pivot['TERMINATA'] = 0

        if not status_pivot.empty:
            # Prepara i dati per Vega-Lite (formato lungo)
            chart_data = status_pivot.reset_index().melt(
                id_vars='AREA',
                var_name='STATO_PdL',
                value_name='Numero di Attività'
            )

            # Specifica Vega-Lite per un grafico a barre impilate senza zoom
            vega_spec = {
                "width": "container",
                "mark": "bar",
                "encoding": {
                    "x": {"field": "AREA", "type": "nominal", "axis": {"title": "Area"}},
                    "y": {"field": "Numero di Attività", "type": "quantitative", "axis": {"title": "Numero di Attività"}},
                    "color": {"field": "STATO_PdL", "type": "nominal", "title": "Stato"},
                    "tooltip": [
                        {"field": "AREA", "type": "nominal"},
                        {"field": "STATO_PdL", "type": "nominal"},
                        {"field": "Numero di Attività", "type": "quantitative"}
                    ]
                },
                "params": []
            }
            st.vega_lite_chart(chart_data, vega_spec, width='stretch')
        else:
            st.info("Nessun dato per il grafico.")
    else:
        st.info("Colonne 'AREA' o 'STATO_PdL' non trovate.")


    st.divider()

    # --- Tabella Dati ---
    st.subheader("Dettaglio Attività Filtrate")
    st.dataframe(filtered_df)


def render_programmazione_tab():
    st.header("Pianificazione Dettagliata Attività")
    st.info("Consulta il dettaglio delle singole attività programmate, filtra per trovare attività specifiche e visualizza lo storico degli interventi.")

    df = carica_dati_attivita_programmate()

    if df.empty:
        st.warning("Nessun dato sulle attività programmate trovato nel database.")
        return

    # --- Filtri ---
    st.subheader("Filtra Attività")
    col1, col2, col3 = st.columns(3)

    with col1:
        pdl_search = st.text_input("Cerca per PdL")

    with col2:
        aree_disponibili = sorted(df['AREA'].dropna().unique()) if 'AREA' in df.columns else []
        area_selezionata = st.multiselect("Filtra per Area", options=aree_disponibili, default=aree_disponibili, key="area_filter_programmazione")

    with col3:
        giorni_settimana = ["LUN", "MAR", "MER", "GIO", "VEN"]
        giorni_selezionati = st.multiselect("Filtra per Giorno", options=giorni_settimana, default=giorni_settimana)

    # Applica filtri
    filtered_df = df.copy()
    if pdl_search:
        filtered_df = filtered_df[filtered_df['PdL'].astype(str).str.contains(pdl_search, case=False, na=False)]
    if area_selezionata:
        filtered_df = filtered_df[filtered_df['AREA'].isin(area_selezionata)]
    if giorni_selezionati:
        mask = pd.Series([False] * len(filtered_df), index=filtered_df.index)
        for giorno in giorni_selezionati:
            if giorno in filtered_df.columns:
                mask |= (filtered_df[giorno].str.lower() == 'x')
        filtered_df = filtered_df[mask]

    st.divider()

    if filtered_df.empty:
        st.info("Nessuna attività corrisponde ai filtri selezionati.")
        return

    # --- Grafico Carico di Lavoro ---
    st.subheader("Carico di Lavoro Settimanale per Area")
    giorni_settimana = ["LUN", "MAR", "MER", "GIO", "VEN"]

    # Prepara i dati per il grafico
    chart_data = []
    for giorno in giorni_settimana:
        if giorno in filtered_df.columns:
            # Filtra le attività per il giorno corrente
            day_activities = filtered_df[filtered_df[giorno].str.lower() == 'x']
            if not day_activities.empty:
                # Conta le attività per area in quel giorno
                area_counts_for_day = day_activities['AREA'].value_counts().to_dict()
                for area, count in area_counts_for_day.items():
                    chart_data.append({'Giorno': giorno, 'Area': area, 'Numero di Attività': count})

    if not chart_data:
        st.info("Nessun dato disponibile per visualizzare il carico di lavoro settimanale.")
    else:
        # Crea un DataFrame e pivottalo per il formato corretto del grafico
        chart_df = pd.DataFrame(chart_data)
        pivot_df = chart_df.pivot(index='Giorno', columns='Area', values='Numero di Attività').fillna(0)

        # Assicura l'ordine corretto dei giorni da LUN a VEN
        pivot_df = pivot_df.reindex(giorni_settimana).fillna(0)

        # Prepara i dati per Vega-Lite
        chart_data = pivot_df.reset_index().melt(
            id_vars='Giorno',
            var_name='Area',
            value_name='Numero di Attività'
        )

        # Specifica Vega-Lite
        vega_spec = {
            "width": "container",
            "mark": "bar",
            "encoding": {
                "x": {"field": "Giorno", "type": "ordinal", "sort": giorni_settimana, "axis": {"title": "Giorno della Settimana"}},
                "y": {"field": "Numero di Attività", "type": "quantitative", "axis": {"title": "Numero di Attività"}},
                "color": {"field": "Area", "type": "nominal", "title": "Area"},
                "tooltip": [
                    {"field": "Giorno", "type": "nominal"},
                    {"field": "Area", "type": "nominal"},
                    {"field": "Numero di Attività", "type": "quantitative"}
                ]
            },
            "params": []
        }
        st.vega_lite_chart(chart_data, vega_spec, width='stretch')

    st.divider()

    # --- Dettaglio Attività (Card) ---
    st.subheader("Dettaglio Attività")
    for index, row in filtered_df.iterrows():
        with st.container(border=True):
            pdl = row.get('PdL', 'N/D')
            descrizione = row.get('DESCRIZIONE_ATTIVITA', 'N/D')
            area = row.get('AREA', 'N/D')
            stato = row.get('STATO_ATTIVITA', 'N/D')

            # Trova i giorni in cui l'attività è programmata
            giorni_programmati = [giorno for giorno in giorni_settimana if str(row.get(giorno, '')).lower() == 'x']
            giorni_str = ", ".join(giorni_programmati) if giorni_programmati else "Non specificato"

            st.markdown(f"**PdL `{pdl}`** - {descrizione}")
            st.caption(f"Area: {area} | Stato: {stato} | Giorno/i: **{giorni_str}**")

            # Storico
            storico_list = row.get('Storico', [])
            if storico_list:
                visualizza_storico_organizzato(storico_list, pdl)
            else:
                st.markdown("*Nessuno storico disponibile per questo PdL.*")
