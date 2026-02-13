from typing import Any

import pandas as pd
import streamlit as st

from constants import ICONS
from modules.db_manager import get_shift_by_id
from modules.shift_management import (
    prendi_turno_da_bacheca_logic,
    rispondi_sostituzione_logic,
)


def render_bacheca_tab(
    df_b: pd.DataFrame, df_u: pd.DataFrame, matricola: str, ruolo: str, m_to_n: dict[str, Any]
) -> None:
    """Sotto-funzione per il tab bacheca."""
    st.subheader("Bacheca Turni")
    avail = df_b[df_b["Stato"] == "Disponibile"].sort_values(
        by="Timestamp_Pubblicazione", ascending=False
    )
    if avail.empty:
        st.info("Bacheca vuota.", icon=ICONS["INFO"])
        return
    for _, entry in avail.iterrows():
        info = get_shift_by_id(entry["ID_Turno"])
        if not info:
            continue
        with st.container(border=True):
            st.markdown(f"**{info['Descrizione']}** ({entry['Ruolo_Originale']})")
            st.caption(
                f"Data: {pd.to_datetime(info['Data']).strftime('%d/%m/%Y')} | "
                f"{info['OrarioInizio']}-{info['OrarioFine']}"
            )
            if (
                not (entry["Ruolo_Originale"] == "Tecnico" and ruolo == "Aiutante")
                and st.button(
                    "Prendi Turno",
                    icon=":material/handshake:",
                    key=f"tk_{entry['ID_Bacheca']}",
                    type="primary",
                )
                and prendi_turno_da_bacheca_logic(matricola, ruolo, entry["ID_Bacheca"])
            ):
                st.rerun()


def render_sostituzioni_tab(df_s: pd.DataFrame, m_to_n: dict[str, Any], matricola: str) -> None:
    """Sotto-funzione per il tab sostituzioni."""
    st.subheader("Richieste di Sostituzione")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### :material/call_received: Ricevute")
        rx = df_s[df_s["Ricevente_Matricola"] == matricola]
        for _, r in rx.iterrows():
            with st.container(border=True):
                st.write(
                    f"**{m_to_n.get(str(r['Richiedente_Matricola']), 'Sconosciuto')}** "
                    f"chiede cambio per {r['ID_Turno']}"
                )
                if st.button(
                    "Accetta", icon=ICONS["CHECK"], key=f"ac_{r['ID_Richiesta']}"
                ) and rispondi_sostituzione_logic(r["ID_Richiesta"], matricola, True):
                    st.rerun()
    with c2:
        st.markdown("#### :material/call_made: Inviate")
        tx = df_s[df_s["Richiedente_Matricola"] == matricola]
        for _, r in tx.iterrows():
            st.caption(
                f"- :material/person: A {m_to_n.get(str(r['Ricevente_Matricola']), 'Sconosciuto')} "
                f"per {r['ID_Turno']}"
            )
