import streamlit as st
import pandas as pd
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

def display_expandable_activity_card(pdl, activity_group, key_prefix, container=st):
    """
    Mostra una "card" per un gruppo di attività con un design a espansione nidificata.

    Args:
        pdl (str): L'identificativo del PdL.
        activity_group (pd.DataFrame): DataFrame filtrato per un unico PdL.
        key_prefix (str): Un prefisso unico per questa sezione per evitare key duplicati.
        container: Il container Streamlit in cui renderizzare la card.
    """
    if activity_group.empty:
        return

    # Pulisce il PdL per usarlo in una chiave
    safe_pdl_key = "".join(c if c.isalnum() else "_" for c in str(pdl))

    # Trova l'intervento più recente per il titolo principale
    latest_activity = activity_group.sort_values(by='DATA CONTROLLO', ascending=False).iloc[0]

    # Prepara i campi per il titolo, gestendo valori mancanti
    descrizione = latest_activity.get('DESCRIZIONE ATTIVITA', 'N/D')
    stato_pdl = latest_activity.get('STATO PdL', 'N/D')

    # Livello 1: Expander principale
    expander_title_l1 = f"{pdl} - {descrizione} - [Stato: {stato_pdl}]"
    with container.expander(expander_title_l1):

        # Ordina gli interventi per data, dal più recente al più vecchio
        sorted_interventions = activity_group.sort_values(by='DATA CONTROLLO', ascending=False)

        for index, intervento in sorted_interventions.iterrows():
            # Livello 2: Expander per ogni intervento
            data_controllo = intervento.get('DATA CONTROLLO')
            data_str = data_controllo.strftime('%d/%m/%Y') if pd.notna(data_controllo) else "Data non disponibile"

            personale = intervento.get('PERSONALE IMPEGATO', 'N/D')

            expander_title_l2 = f"Dettaglio intervento del {data_str} - TECNICO: {personale}"

            # Crea una chiave unica per il secondo livello di expander
            l2_key = f"{key_prefix}_{safe_pdl_key}_intervento_{index}"

            with st.expander(expander_title_l2, expanded=False):
                # Livello 3: Contenuto dell'intervento (il report)
                report = intervento.get('STATO ATTIVITA', 'Nessun report per questo intervento.')
                st.text_area(
                    "Report:",
                    value=report,
                    disabled=True,
                    height=150,
                    key=f"{key_prefix}_{safe_pdl_key}_report_{index}" # Chiave unica per il text_area
                )
