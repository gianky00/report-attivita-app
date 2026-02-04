"""
Interfaccia per la creazione e programmazione dei nuovi turni tecnici.
Gestisce turni di assistenza e straordinari con allocazione dei posti.
"""

import datetime

import streamlit as st

from modules.db_manager import create_shift, get_all_users
from modules.notifications import crea_notifica


def render_new_shift_form():
    """Form per la creazione di un nuovo turno da parte del caposquadra."""
    with st.form("new_shift_form", clear_on_submit=True):
        st.subheader("Dettagli Nuovo Turno")
        tipo_turno = st.selectbox("Tipo Turno", ["Assistenza", "Straordinario"])
        desc_turno = st.text_input(
            "Descrizione Turno (es. 'Mattina', 'Straordinario Sabato')"
        )
        data_turno = st.date_input("Data Turno")
        col1, col2 = st.columns(2)
        ora_inizio = col1.time_input("Orario Inizio", datetime.time(8, 0))
        ora_fine = col2.time_input("Orario Fine", datetime.time(17, 0))
        col3, col4 = st.columns(2)
        posti_tech = col3.number_input("Numero Posti Tecnico", min_value=0, step=1)
        posti_aiut = col4.number_input("Numero Posti Aiutante", min_value=0, step=1)

        if st.form_submit_button("Crea Turno"):
            if not desc_turno:
                st.error("La descrizione non può essere vuota.")
            else:
                new_id = f"T_{int(datetime.datetime.now().timestamp())}"
                new_shift_data = {
                    "ID_Turno": new_id,
                    "Descrizione": desc_turno,
                    "Data": data_turno.isoformat(),
                    "OrarioInizio": ora_inizio.strftime("%H:%M"),
                    "OrarioFine": ora_fine.strftime("%H:%M"),
                    "PostiTecnico": posti_tech,
                    "PostiAiutante": posti_aiut,
                    "Tipo": tipo_turno,
                }
                if create_shift(new_shift_data):
                    st.success(f"Turno '{desc_turno}' creato con successo!")
                    df_contatti = get_all_users()
                    if not df_contatti.empty:
                        utenti_da_notificare = df_contatti["Matricola"].tolist()
                        data_str = data_turno.strftime("%d/%m/%Y")
                        messaggio = (
                            f"📢 Nuovo turno disponibile: '{desc_turno}' "
                            f"il {data_str}."
                        )
                        for matricola in utenti_da_notificare:
                            crea_notifica(matricola, messaggio)
                    st.rerun()
                else:
                    st.error("Errore nel salvataggio del nuovo turno.")
