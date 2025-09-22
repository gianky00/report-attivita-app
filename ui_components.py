import streamlit as st
import streamlit.components.v1 as components

def render_status_indicator():
    """
    Renders a component that displays the browser's online/offline status
    and returns the status string ('online' or 'offline') to the Python backend.
    """
    html_code = f"""
    <div id="status-indicator-container" style="position: fixed; top: 10px; right: 10px; z-index: 1000; background-color: white; padding: 5px 10px; border-radius: 8px; border: 1px solid #dcdcdc; font-family: sans-serif; font-size: 14px; box-shadow: 0 1px 3px rgba(0,0,0,0.12), 0 1px 2px rgba(0,0,0,0.24);">
        <div id="status-indicator"></div>
    </div>
    <script>
        const statusIndicator = document.getElementById('status-indicator');

        function updateOnlineStatus() {{
            const isOnline = navigator.onLine;
            let statusValue;
            if (isOnline) {{
                statusIndicator.innerHTML = '<span>🟢 Connesso</span>';
                statusValue = 'online';
            }} else {{
                statusIndicator.innerHTML = '<span>🔴 Offline</span>';
                statusValue = 'offline';
            }}
            // Send the status back to Streamlit.
            // For st.components.v1.html, we don't need a key. Streamlit knows
            // which component sent the message.
            window.parent.postMessage({{
                isStreamlitMessage: true,
                type: 'streamlit:setComponentValue',
                value: statusValue
            }}, '*');
        }}

        window.addEventListener('online', updateOnlineStatus);
        window.addEventListener('offline', updateOnlineStatus);

        setTimeout(updateOnlineStatus, 100);
    </script>
    """

    # The 'key' argument is not supported by st.components.v1.html
    online_status = components.html(html_code, height=0, width=0)

    return online_status or 'online'

def _find_column(df, keywords):
    """Helper function to find a column in a dataframe that contains all keywords."""
    for col in df.columns:
        if all(keyword.lower() in col.lower() for keyword in keywords):
            return col
    return None

def display_expandable_activity_card(pdl, activity_group, key_prefix, container=st):
    """
    Mostra una "card" per un gruppo di attività con un design a espansione nidificata.
    Questa versione è robusta e trova i nomi delle colonne dinamicamente.
    """
    if activity_group.empty:
        return

    # Importa pandas qui dentro per rendere il componente autocontenuto
    import pandas as pd

    # Trova dinamicamente i nomi delle colonne
    col_desc = _find_column(activity_group, ['descrizione', 'attivita'])
    col_stato_pdl = _find_column(activity_group, ['stato', 'pdl'])
    col_data = _find_column(activity_group, ['data', 'controllo'])
    col_personale = _find_column(activity_group, ['personale', 'impiegato'])
    col_report = _find_column(activity_group, ['stato', 'attivita'])

    # Pulisce il PdL per usarlo in una chiave
    safe_pdl_key = "".join(c if c.isalnum() else "_" for c in str(pdl))

    # Trova l'intervento più recente per il titolo principale
    latest_activity = activity_group.sort_values(by=col_data, ascending=False).iloc[0] if col_data else activity_group.iloc[0]

    descrizione = latest_activity.get(col_desc, 'N/D') if col_desc else 'Descrizione non trovata'
    stato_pdl = latest_activity.get(col_stato_pdl, 'N/D') if col_stato_pdl else 'Stato non trovato'

    # Livello 1: Expander principale
    expander_title_l1 = f"{pdl} - {descrizione} - [Stato: {stato_pdl}]"
    with container.expander(expander_title_l1):

        # Ordina gli interventi per data, dal più recente al più vecchio
        sorted_interventions = activity_group.sort_values(by=col_data, ascending=False) if col_data else activity_group

        for index, intervento in sorted_interventions.iterrows():
            # Livello 2: Expander per ogni intervento
            data_controllo = intervento.get(col_data) if col_data else None
            data_str = data_controllo.strftime('%d/%m/%Y') if pd.notna(data_controllo) else "Data non disponibile"

            personale = intervento.get(col_personale, 'N/D') if col_personale else "Personale non trovato"

            expander_title_l2 = f"Dettaglio intervento del {data_str} - TECNICO: {personale}"

            l2_key = f"{key_prefix}_{safe_pdl_key}_intervento_{index}"

            with st.expander(expander_title_l2, expanded=False):
                # Livello 3: Contenuto dell'intervento (il report)
                report = intervento.get(col_report, 'Nessun report per questo intervento.') if col_report else "Colonna report non trovata"
                st.text_area(
                    "Report:",
                    value=report,
                    disabled=True,
                    height=150,
                    key=f"{key_prefix}_{safe_pdl_key}_report_{index}"
                )
