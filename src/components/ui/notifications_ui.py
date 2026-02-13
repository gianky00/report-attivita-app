"""
Componenti UI per il centro notifiche.
"""

from typing import Any

import pandas as pd
import streamlit as st

from modules.notifications import segna_notifica_letta


def render_notification_center(
    notifications: list[dict[str, Any]] | pd.DataFrame, matricola_utente: str
) -> None:
    """Disegna il popover del centro notifiche."""
    # Assicura che sia un DataFrame
    df = pd.DataFrame(notifications) if isinstance(notifications, list) else notifications

    # Se vuoto o manca la colonna Stato, crea un DF vuoto con le colonne giuste
    if df.empty or "Stato" not in df.columns:
        unread_count = 0
        df = pd.DataFrame(columns=["ID_Notifica", "Timestamp", "Messaggio", "Stato"])
    else:
        unread_count = len(df[df["Stato"] == "non letta"])

    from constants import ICONS

    label = f" {unread_count}" if unread_count > 0 else ""
    icon = ICONS["NOTIFICATIONS"]

    with st.popover(label, icon=icon):
        st.subheader("Notifiche")
        if df.empty:
            st.write("Nessuna notifica.")
        else:
            for _, n in df.iterrows():
                is_unread = n["Stato"] == "non letta"
                col1, col2 = st.columns([4, 1])
                with col1:
                    style = "**" if is_unread else "<span style='color: grey;'>"
                    end = "**" if is_unread else "</span>"
                    st.markdown(f"{style}{n['Messaggio']}{end}", unsafe_allow_html=True)
                    try:
                        ts = pd.to_datetime(n["Timestamp"]).strftime("%d/%m/%Y %H:%M")
                        st.caption(ts)
                    except Exception:
                        st.caption(n["Timestamp"])
                if is_unread:
                    with col2:
                        if st.button("letto", key=f"read_{n['ID_Notifica']}"):
                            segna_notifica_letta(n["ID_Notifica"])
                            st.rerun()
                st.divider()
