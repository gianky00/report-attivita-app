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

def display_activity_card(activity_group, key_prefix, container=st):
    """
    Mostra una "card" per un gruppo di attività relative a un singolo PdL.

    Args:
        activity_group (pd.DataFrame): DataFrame filtrato per un unico PdL.
        key_prefix (str): Un prefisso unico per questa sezione per evitare key duplicati.
        container: Il container Streamlit in cui renderizzare la card (es. st o una colonna).
    """
    if activity_group.empty:
        return

    # Ordina per data per trovare l'intervento più recente
    # Assumiamo che la colonna 'DATA CONTROLLO' esista e sia in formato datetime
    if 'DATA CONTROLLO' in activity_group.columns:
        activity_group['DATA CONTROLLO'] = pd.to_datetime(activity_group['DATA CONTROLLO'], errors='coerce')
        latest_activity = activity_group.sort_values(by='DATA CONTROLLO', ascending=False).iloc[0]
    else:
        # Se manca la data, prendi la prima riga come rappresentativa
        latest_activity = activity_group.iloc[0]

    pdl = latest_activity.get('PdL', 'N/D')
    descrizione = latest_activity.get('Descrizione', 'Nessuna descrizione')

    # Pulisce il PdL per usarlo in una chiave, rimuovendo caratteri non sicuri
    safe_pdl_key = "".join(c if c.isalnum() else "_" for c in str(pdl))

    expander_title = f"**{pdl}** - {descrizione}"

    with container.expander(expander_title):
        # --- Dettagli Principali (dall'attività più recente) ---
        col1, col2, col3 = st.columns(3)
        col1.metric("Stato", latest_activity.get('Stato', 'N/D'))
        col2.metric("Area", latest_activity.get('Area', 'N/D'))
        col3.metric("TCL", latest_activity.get('TCL', 'N/D'))

        st.markdown("---")

        # --- Report e Dettagli Tecnici ---
        st.subheader("Dettagli Ultimo Intervento")

        data_controllo_str = latest_activity['DATA CONTROLLO'].strftime('%d/%m/%Y') if pd.notna(latest_activity['DATA CONTROLLO']) else 'Non specificata'
        st.info(f"**Data Controllo:** {data_controllo_str}")

        personale = latest_activity.get('PERSONALE IMPEGATO', 'Non specificato')
        st.info(f"**Personale Impiegato:** {personale}")

        report = latest_activity.get('Report', 'Nessun report compilato.')
        st.text_area("Report Attività", value=report, height=150, disabled=True, key=f"{key_prefix}_report_text_{safe_pdl_key}")

        # --- Storico Interventi ---
        if len(activity_group) > 1:
            st.markdown("---")
            st.subheader("Storico Interventi")

            # Mostra gli interventi più vecchi
            storico_df = activity_group.iloc[1:]

            for _, row in storico_df.iterrows():
                data_storico_str = row['DATA CONTROLLO'].strftime('%d/%m/%Y') if pd.notna(row['DATA CONTROLLO']) else 'N/D'
                st.markdown(f"- **{data_storico_str}**: {row.get('Report', 'Nessun report.')[:80]}...")
