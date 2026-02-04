"""
Componenti UI per il centro notifiche.
"""
import pandas as pd
import streamlit as st
from modules.notifications import segna_notifica_letta

def render_notification_center(notifications_df, matricola_utente):
    """Disegna il popover del centro notifiche."""
    unread = notifications_df[notifications_df["Stato"] == "non letta"]
    icon = f"🔔 {len(unread)}" if not unread.empty else "🔔"

    with st.popover(icon):
        st.subheader("Notifiche")
        if notifications_df.empty:
            st.write("Nessuna notifica.")
        else:
            for _, n in notifications_df.iterrows():
                is_unread = n["Stato"] == "non letta"
                col1, col2 = st.columns([4, 1])
                with col1:
                    style = "**" if is_unread else "<span style='color: grey;'>"
                    end = "**" if is_unread else "</span>"
                    st.markdown(f"{style}{n['Messaggio']}{end}", unsafe_allow_html=True)
                    st.caption(pd.to_datetime(n["Timestamp"]).strftime("%d/%m/%Y %H:%M"))
                if is_unread:
                    with col2:
                        if st.button("letto", key=f"read_{n['ID_Notifica']}"):
                            segna_notifica_letta(n['ID_Notifica'])
                            st.rerun()
                st.divider()
