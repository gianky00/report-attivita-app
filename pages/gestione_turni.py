import streamlit as st
import pandas as pd
import datetime
import subprocess
import os

# Importa le funzioni logiche necessarie dai moduli
from modules.pdf_utils import generate_on_call_pdf
from modules.shift_management import (
    prenota_turno_logic,
    cancella_prenotazione_logic,
    richiedi_sostituzione_logic,
    rispondi_sostituzione_logic,
    pubblica_turno_in_bacheca_logic,
    prendi_turno_da_bacheca_logic,
    manual_override_logic
)
from modules.db_manager import (
    get_shifts_by_type,
    get_all_bookings,
    get_all_users,
    get_all_bacheca_items,
    get_all_substitutions,
    get_shift_by_id
)

# Mantieni questa funzione all'interno del modulo per coerenza
def render_turni_list(df_turni, df_bookings, df_users, matricola_utente, ruolo, key_suffix):
    if df_turni.empty:
        st.info("Nessun turno di questo tipo disponibile al momento.")
        return

    mostra_solo_disponibili = st.checkbox("Mostra solo turni con posti disponibili", key=f"filter_turni_{key_suffix}")
    matricola_to_name = pd.Series(df_users['Nome Cognome'].values, index=df_users['Matricola'].astype(str)).to_dict()

    if ruolo == "Amministratore":
        search_term_turni = st.text_input("Cerca per descrizione del turno...", key=f"search_turni_{key_suffix}")
        if search_term_turni:
            df_turni = df_turni[df_turni['Descrizione'].str.contains(search_term_turni, case=False, na=False)]

    st.divider()
    if df_turni.empty:
        st.info("Nessun turno corrisponde alla ricerca.")

    for index, turno in df_turni.iterrows():
        prenotazioni_turno = df_bookings[df_bookings['ID_Turno'] == turno['ID_Turno']]
        posti_tecnico = int(turno['PostiTecnico'])
        posti_aiutante = int(turno['PostiAiutante'])
        tecnici_prenotati = len(prenotazioni_turno[prenotazioni_turno['RuoloOccupato'] == 'Tecnico'])
        aiutanti_prenotati = len(prenotazioni_turno[prenotazioni_turno['RuoloOccupato'] == 'Aiutante'])

        is_available = (tecnici_prenotati < posti_tecnico) or (aiutanti_prenotati < posti_aiutante)
        if mostra_solo_disponibili and not is_available:
            continue

        with st.container(border=True):
            st.markdown(f"**{turno['Descrizione']}**")
            st.caption(f"{pd.to_datetime(turno['Data']).strftime('%d/%m/%Y')} | {turno['OrarioInizio']} - {turno['OrarioFine']}")

            tech_icon = "✅" if tecnici_prenotati < posti_tecnico else "❌"
            aiut_icon = "✅" if aiutanti_prenotati < posti_aiutante else "❌"
            st.markdown(f"**Posti:** `Tecnici: {tecnici_prenotati}/{posti_tecnico}` {tech_icon} | `Aiutanti: {aiutanti_prenotati}/{posti_aiutante}` {aiut_icon}")

            if not prenotazioni_turno.empty:
                st.markdown("**Personale Prenotato:**")
                for _, p in prenotazioni_turno.iterrows():
                    matricola = str(p['Matricola'])
                    nome_utente = matricola_to_name.get(matricola, f"Matricola {matricola}")
                    st.markdown(f"- {nome_utente} (*{p['RuoloOccupato']}*)")

            st.markdown("---")

            prenotazione_utente = prenotazioni_turno[prenotazioni_turno['Matricola'] == str(matricola_utente)]

            if not prenotazione_utente.empty:
                st.success("Sei prenotato per questo turno.")
                col1, col2, col3 = st.columns(3)
                if col1.button("Cancella Prenotazione", key=f"del_{turno['ID_Turno']}_{key_suffix}"):
                    if cancella_prenotazione_logic(matricola_utente, turno['ID_Turno']):
                        st.rerun()
                if col2.button("📢 Pubblica in Bacheca", key=f"pub_{turno['ID_Turno']}_{key_suffix}"):
                    if pubblica_turno_in_bacheca_logic(matricola_utente, turno['ID_Turno']):
                        st.rerun()
                if col3.button("🔄 Chiedi Sostituzione", key=f"ask_{turno['ID_Turno']}_{key_suffix}"):
                    st.session_state['sostituzione_turno_id'] = turno['ID_Turno']
                    st.rerun()
            else:
                opzioni = []
                if tecnici_prenotati < posti_tecnico: opzioni.append("Tecnico")
                if aiutanti_prenotati < posti_aiutante: opzioni.append("Aiutante")
                if opzioni:
                    ruolo_scelto = st.selectbox("Prenota come:", opzioni, key=f"sel_{turno['ID_Turno']}_{key_suffix}")
                    if st.button("Conferma Prenotazione", key=f"add_{turno['ID_Turno']}_{key_suffix}"):
                        if prenota_turno_logic(matricola_utente, turno['ID_Turno'], ruolo_scelto):
                            st.rerun()
                else:
                    st.warning("Turno al completo.")

            if st.session_state.get('sostituzione_turno_id') == turno['ID_Turno']:
                st.markdown("---")
                st.markdown("**A chi vuoi chiedere il cambio?**")

                ricevente_options = [str(m) for m in df_users['Matricola'] if str(m) != str(matricola_utente)]
                ricevente_matricola = st.selectbox("Seleziona collega:", ricevente_options, format_func=lambda m: matricola_to_name.get(m, m), key=f"swap_select_{turno['ID_Turno']}_{key_suffix}")

                if st.button("Invia Richiesta", key=f"swap_confirm_{turno['ID_Turno']}_{key_suffix}"):
                    if richiedi_sostituzione_logic(matricola_utente, ricevente_matricola, turno['ID_Turno']):
                        del st.session_state['sostituzione_turno_id']
                        st.rerun()

def render_reperibilita_tab(df_prenotazioni, df_contatti, matricola_utente, ruolo_utente):
    st.subheader("📅 Calendario Reperibilità Settimanale")

    HOLIDAYS_2025 = [
        datetime.date(2025, 1, 1), datetime.date(2025, 1, 6), datetime.date(2025, 4, 20),
        datetime.date(2025, 4, 21), datetime.date(2025, 4, 25), datetime.date(2025, 5, 1),
        datetime.date(2025, 6, 2), datetime.date(2025, 8, 15), datetime.date(2025, 11, 1),
        datetime.date(2025, 12, 8), datetime.date(2025, 12, 13), # Santa Lucia
        datetime.date(2025, 12, 25), datetime.date(2025, 12, 26),
    ]
    WEEKDAY_NAMES_IT = ["Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"]
    MESI_ITALIANI = ["Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno", "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"]
    today = datetime.date.today()

    df_turni_reperibilita = get_shifts_by_type('Reperibilità')

    if 'editing_oncall_shift_id' in st.session_state and st.session_state.editing_oncall_shift_id:
        shift_id_to_edit = st.session_state.editing_oncall_shift_id
        turno_info = get_shift_by_id(shift_id_to_edit)
        with st.container(border=True):
            st.subheader(f"Modifica Assegnazione per il {pd.to_datetime(turno_info['Data']).strftime('%d/%m/%Y')}")

            all_users = get_all_users()
            user_list = all_users['Matricola'].tolist()
            user_dict = pd.Series(all_users['Nome Cognome'].values, index=all_users['Matricola']).to_dict()

            new_tech1 = st.selectbox("Seleziona Tecnico 1:", options=user_list, format_func=lambda x: user_dict.get(x, x))
            new_tech2 = st.selectbox("Seleziona Tecnico 2:", options=user_list, format_func=lambda x: user_dict.get(x, x), index=1 if len(user_list) > 1 else 0)

            col1, col2 = st.columns(2)
            with col1:
                if st.button("Salva Modifiche", type="primary"):
                    if manual_override_logic(shift_id_to_edit, new_tech1, new_tech2, matricola_utente):
                        st.success("Assegnazione modificata con successo!")
                        del st.session_state.editing_oncall_shift_id
                        st.rerun()
                    else:
                        st.error("Errore durante il salvataggio delle modifiche.")
            with col2:
                if st.button("Annulla"):
                    del st.session_state.editing_oncall_shift_id
                    st.rerun()
        st.stop()

    if 'managing_oncall_shift_id' in st.session_state and st.session_state.managing_oncall_shift_id:
        shift_id_to_manage = st.session_state.managing_oncall_shift_id
        matricola_to_manage = st.session_state.managing_oncall_user_matricola
        user_to_manage_name = df_contatti[df_contatti['Matricola'] == matricola_to_manage].iloc[0]['Nome Cognome']

        with st.container(border=True):
            st.subheader("Gestione Turno di Reperibilità")
            turno_info = get_shift_by_id(shift_id_to_manage)
            if turno_info:
                st.write(f"Stai modificando il turno di **{user_to_manage_name}** per il giorno **{pd.to_datetime(turno_info['Data']).strftime('%d/%m/%Y')}**.")
            else:
                st.error("Dettagli del turno non trovati.")
                if st.button("⬅️ Torna al Calendario"):
                     if 'managing_oncall_shift_id' in st.session_state: del st.session_state.managing_oncall_shift_id
                     st.rerun()
                st.stop()

            if st.session_state.get('oncall_swap_mode'):
                st.markdown("**A chi vuoi chiedere il cambio?**")
                contatti_validi = df_contatti[
                    (df_contatti['Matricola'] != matricola_to_manage) &
                    (df_contatti['PasswordHash'].notna())
                ]
                matricola_to_name = pd.Series(contatti_validi['Nome Cognome'].values, index=contatti_validi['Matricola']).to_dict()
                ricevente_matricola = st.selectbox("Seleziona collega:", contatti_validi['Matricola'].tolist(), format_func=lambda m: matricola_to_name.get(m, m), key=f"swap_select_{shift_id_to_manage}")

                c1, c2 = st.columns(2)
                if c1.button("Invia Richiesta", key=f"swap_confirm_{shift_id_to_manage}", type="primary"):
                    if richiedi_sostituzione_logic(matricola_to_manage, ricevente_matricola, shift_id_to_manage):
                        del st.session_state.managing_oncall_shift_id
                        if 'oncall_swap_mode' in st.session_state: del st.session_state.oncall_swap_mode
                        st.rerun()
                if c2.button("Annulla Scambio"):
                    del st.session_state.oncall_swap_mode
                    st.rerun()
            else:
                st.info("Cosa vuoi fare con questo turno?")
                col1, col2 = st.columns(2)
                if col1.button("📢 Pubblica in Bacheca"):
                    if pubblica_turno_in_bacheca_logic(matricola_to_manage, shift_id_to_manage):
                        del st.session_state.managing_oncall_shift_id
                        st.rerun()
                if col2.button("🔄 Chiedi Sostituzione"):
                    st.session_state.oncall_swap_mode = True
                    st.rerun()

            st.divider()
            if st.button("⬅️ Torna al Calendario", key=f"cancel_manage_{shift_id_to_manage}"):
                if 'managing_oncall_shift_id' in st.session_state: del st.session_state.managing_oncall_shift_id
                if 'managing_oncall_user_matricola' in st.session_state: del st.session_state.managing_oncall_user_matricola
                if 'oncall_swap_mode' in st.session_state: del st.session_state.oncall_swap_mode
                st.rerun()
        st.stop()

    if 'week_start_date' not in st.session_state:
        st.session_state.week_start_date = today - datetime.timedelta(days=today.weekday())

    # Filtri per mese e anno e pulsanti di azione
    filter_cols = st.columns([2, 2, 3, 3])
    with filter_cols[0]:
        selected_year = st.selectbox("Anno", list(range(today.year - 2, today.year + 3)), index=2, label_visibility="collapsed")
    with filter_cols[1]:
        selected_month = st.selectbox("Mese", MESI_ITALIANI, index=today.month - 1, label_visibility="collapsed")
    with filter_cols[2]:
        if st.button("Vai al mese", use_container_width=True):
            first_day_of_month = datetime.date(selected_year, MESI_ITALIANI.index(selected_month) + 1, 1)
            st.session_state.week_start_date = first_day_of_month - datetime.timedelta(days=first_day_of_month.weekday())
            st.rerun()
    with filter_cols[3]:
        if st.button("Sett. Corrente", use_container_width=True):
            st.session_state.week_start_date = today - datetime.timedelta(days=today.weekday())
            st.rerun()

    st.divider()

    # Pulsante per esportare il PDF
    if st.button("Esporta PDF", use_container_width=True):
        month_name = selected_month
        month_number = MESI_ITALIANI.index(month_name) + 1

        # Filtra i turni per il mese e anno selezionati
        oncall_shifts_df = df_turni_reperibilita.copy()
        oncall_shifts_df['Data'] = pd.to_datetime(oncall_shifts_df['Data'])

        monthly_shifts = oncall_shifts_df[
            (oncall_shifts_df['Data'].dt.month == month_number) &
            (oncall_shifts_df['Data'].dt.year == selected_year)
        ]

        # Prepara i dati per il PDF
        bookings_for_month = df_prenotazioni[df_prenotazioni['ID_Turno'].isin(monthly_shifts['ID_Turno'])]

        if not bookings_for_month.empty:
            merged_data = pd.merge(bookings_for_month, df_contatti, on='Matricola')
            merged_data = pd.merge(merged_data, monthly_shifts, on='ID_Turno')

            pdf_data = merged_data[['Data', 'Nome Cognome', 'RuoloOccupato']].to_dict('records')

            # Genera il PDF
            pdf_path = generate_on_call_pdf(pdf_data, month_name, selected_year)

            if pdf_path:
                # Invia l'email con il PDF in allegato
                subject = f"Report Reperibilità {month_name} {selected_year}"
                body = f"In allegato il report della reperibilità per il mese di {month_name} {selected_year}."

                try:
                    subprocess.run(["python", "send_email_subprocess.py", subject, body, pdf_path], check=True)
                    st.success("Email con il report PDF inviata con successo!")

                    # Rimuovi il file PDF dopo l'invio
                    os.remove(pdf_path)
                except (subprocess.CalledProcessError, FileNotFoundError) as e:
                    st.error(f"Errore durante l'invio dell'email: {e}")

            else:
                st.warning("Nessun dato di reperibilità da esportare per il mese selezionato.")
        else:
            st.warning("Nessuna prenotazione trovata per il mese selezionato.")

    # Interfaccia di navigazione settimanale compatta
    nav_cols = st.columns([1, 10, 1])
    with nav_cols[0]:
        if st.button("⬅️", use_container_width=True):
            st.session_state.week_start_date -= datetime.timedelta(days=7)
            st.rerun()

    with nav_cols[1]:
        start_date = st.session_state.week_start_date
        end_date = start_date + datetime.timedelta(days=6)

        # Formattazione con mese in italiano
        start_month_it = MESI_ITALIANI[start_date.month - 1][:3]
        end_month_it = MESI_ITALIANI[end_date.month - 1][:3]

        if start_date.year != end_date.year:
             start_date_str = f"{start_date.day} {start_month_it} {start_date.year}"
             end_date_str = f"{end_date.day} {end_month_it} {end_date.year}"
        elif start_date.month != end_date.month:
            start_date_str = f"{start_date.day} {start_month_it}"
            end_date_str = f"{end_date.day} {end_month_it} {end_date.year}"
        else:
            start_date_str = f"{start_date.day}"
            end_date_str = f"{end_date.day} {end_month_it} {end_date.year}"

        st.markdown(f"<h5 style='text-align: center; white-space: nowrap;'>{start_date_str} - {end_date_str}</h5>", unsafe_allow_html=True)

    with nav_cols[2]:
        if st.button("➡️", use_container_width=True):
            st.session_state.week_start_date += datetime.timedelta(days=7)
            st.rerun()

    st.divider()

    oncall_shifts_df = df_turni_reperibilita.copy()
    oncall_shifts_df['Data'] = pd.to_datetime(oncall_shifts_df['Data'], format='mixed', errors='coerce')
    oncall_shifts_df['date_only'] = oncall_shifts_df['Data'].dt.date

    week_dates = [st.session_state.week_start_date + datetime.timedelta(days=i) for i in range(7)]
    cols = st.columns(7)

    for i, day in enumerate(week_dates):
        with cols[i]:
            is_today = (day == today)
            is_sunday = day.weekday() == 6
            is_holiday = day in HOLIDAYS_2025
            is_special_day = is_sunday or is_holiday

            border_style = "2px solid #007bff" if is_today else "1px solid #d3d3d3"
            day_color = "red" if is_special_day else "inherit"
            background_color = "#e0f7fa" if is_today else ("#fff0f0" if is_special_day else "white")

            technicians_html = ""
            shift_today = oncall_shifts_df[oncall_shifts_df['date_only'] == day]
            user_is_on_call = False
            shift_id_today = None
            managed_user_matricola = matricola_utente

            if not shift_today.empty:
                shift_id_today = shift_today.iloc[0]['ID_Turno']
                prenotazioni_today = df_prenotazioni[df_prenotazioni['ID_Turno'] == shift_id_today]
                matricola_to_name = pd.Series(df_contatti['Nome Cognome'].values, index=df_contatti['Matricola'].astype(str)).to_dict()

                if not prenotazioni_today.empty:
                    tech_display_list = []
                    for _, booking in prenotazioni_today.iterrows():
                        technician_matricola = str(booking['Matricola'])
                        technician_name = matricola_to_name.get(technician_matricola, f"Matricola {technician_matricola}")
                        surname = technician_name.split()[-1].upper()
                        tech_display_list.append(surname)
                        if technician_matricola == str(matricola_utente):
                            user_is_on_call = True
                    if tech_display_list:
                        managed_user_matricola = str(prenotazioni_today.iloc[0]['Matricola'])
                    technicians_html = "".join([f"<div style='font-size: 0.9em; font-weight: 500; line-height: 1.3; margin-bottom: 2px;'>{s}</div>" for s in tech_display_list])
                else:
                    technicians_html = "<span style='color: grey; font-style: italic;'>Libero</span>"
            else:
                 technicians_html = "<span style='color: grey; font-style: italic;'>N/D</span>"

            st.markdown(
                f"""
                <div style="border: {border_style}; border-radius: 8px; padding: 8px; background-color: {background_color}; height: 140px; display: flex; flex-direction: column; justify-content: space-between;">
                    <div style="display: flex; justify-content: space-between; align-items: flex-start; width: 100%;">
                        <div style="text-align: left;">
                            <p style="font-weight: bold; color: {day_color}; margin: 0; font-size: 0.9em;">{WEEKDAY_NAMES_IT[day.weekday()]}</p>
                            <h3 style="margin: 0; color: {day_color};">{day.day}</h3>
                        </div>
                        <div style="text-align: right; padding-left: 5px;">
                            {technicians_html}
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True
            )

            can_manage = (user_is_on_call or ruolo_utente == "Amministratore") and shift_id_today
            if can_manage:
                action_cols = st.columns(2)
                with action_cols[0]:
                    if st.button("Gestisci", key=f"manage_{day}", use_container_width=True):
                        st.session_state.managing_oncall_shift_id = shift_id_today
                        st.session_state.managing_oncall_user_matricola = managed_user_matricola
                        st.rerun()
                with action_cols[1]:
                    if ruolo_utente == "Amministratore":
                        if st.button("Modifica", key=f"edit_{day}", use_container_width=True):
                            st.session_state.editing_oncall_shift_id = shift_id_today
                            st.rerun()

def render_gestione_turni_tab(matricola_utente, ruolo):
    st.subheader("Gestione Turni")

    # Caricamento centralizzato dei dati all'inizio
    df_bookings = get_all_bookings()
    df_users = get_all_users()
    df_bacheca = get_all_bacheca_items()
    df_substitutions = get_all_substitutions()

    matricola_to_name = pd.Series(df_users['Nome Cognome'].values, index=df_users['Matricola'].astype(str)).to_dict()

    turni_disponibili_tab, bacheca_tab, sostituzioni_tab = st.tabs(["📅 Turni", "📢 Bacheca", "🔄 Sostituzioni"])

    with turni_disponibili_tab:
        assistenza_tab, straordinario_tab, reperibilita_tab = st.tabs(["Turni Assistenza", "Turni Straordinario", "Turni Reperibilità"])
        with assistenza_tab:
            df_assistenza = get_shifts_by_type('Assistenza')
            render_turni_list(df_assistenza, df_bookings, df_users, matricola_utente, ruolo, "assistenza")
        with straordinario_tab:
            df_straordinario = get_shifts_by_type('Straordinario')
            render_turni_list(df_straordinario, df_bookings, df_users, matricola_utente, ruolo, "straordinario")
        with reperibilita_tab:
            render_reperibilita_tab(df_bookings, df_users, matricola_utente, ruolo)

    with bacheca_tab:
        st.subheader("Turni Liberi in Bacheca")
        turni_disponibili_bacheca = df_bacheca[df_bacheca['Stato'] == 'Disponibile'].sort_values(by='Timestamp_Pubblicazione', ascending=False)
        if turni_disponibili_bacheca.empty:
            st.info("Al momento non ci sono turni liberi in bacheca.")
        else:
            for _, bacheca_entry in turni_disponibili_bacheca.iterrows():
                turno_details = get_shift_by_id(bacheca_entry['ID_Turno'])
                if not turno_details:
                    st.warning(f"Dettagli non trovati per il turno ID {bacheca_entry['ID_Turno']}. Potrebbe essere stato rimosso.")
                    continue

                matricola_originale = str(bacheca_entry['Tecnico_Originale_Matricola'])
                nome_originale = matricola_to_name.get(matricola_originale, f"Matricola {matricola_originale}")
                with st.container(border=True):
                    st.markdown(f"**{turno_details['Descrizione']}** ({bacheca_entry['Ruolo_Originale']})")
                    st.caption(f"Data: {pd.to_datetime(turno_details['Data']).strftime('%d/%m/%Y')} | Orario: {turno_details['OrarioInizio']} - {turno_details['OrarioFine']}")
                    st.write(f"Pubblicato da: {nome_originale} il {pd.to_datetime(bacheca_entry['Timestamp_Pubblicazione']).strftime('%d/%m %H:%M')}")
                    ruolo_richiesto = bacheca_entry['Ruolo_Originale']
                    is_eligible = not (ruolo_richiesto == 'Tecnico' and ruolo == 'Aiutante')
                    if is_eligible:
                        if st.button("Prendi questo turno", key=f"take_{bacheca_entry['ID_Bacheca']}"):
                            if prendi_turno_da_bacheca_logic(matricola_utente, ruolo, bacheca_entry['ID_Bacheca']):
                                st.rerun()
                    else:
                        st.info("Non hai il ruolo richiesto per questo turno.")

    with sostituzioni_tab:
        st.subheader("Richieste di Sostituzione")
        st.markdown("#### 📥 Richieste Ricevute")
        richieste_ricevute = df_substitutions[df_substitutions['Ricevente_Matricola'] == str(matricola_utente)]
        if richieste_ricevute.empty:
            st.info("Nessuna richiesta di sostituzione ricevuta.")
        for _, richiesta in richieste_ricevute.iterrows():
            with st.container(border=True):
                richiedente_nome = matricola_to_name.get(str(richiesta['Richiedente_Matricola']), "Sconosciuto")
                st.markdown(f"**{richiedente_nome}** ti ha chiesto un cambio per il turno **{richiesta['ID_Turno']}**.")
                c1, c2 = st.columns(2)
                if c1.button("✅ Accetta", key=f"acc_{richiesta['ID_Richiesta']}"):
                    if rispondi_sostituzione_logic(richiesta['ID_Richiesta'], matricola_utente, True):
                        st.rerun()
                if c2.button("❌ Rifiuta", key=f"rif_{richiesta['ID_Richiesta']}"):
                    if rispondi_sostituzione_logic(richiesta['ID_Richiesta'], matricola_utente, False):
                        st.rerun()
        st.divider()
        st.markdown("#### 📤 Richieste Inviate")
        richieste_inviate = df_substitutions[df_substitutions['Richiedente_Matricola'] == str(matricola_utente)]
        if richieste_inviate.empty:
            st.info("Nessuna richiesta di sostituzione inviata.")
        for _, richiesta in richieste_inviate.iterrows():
            ricevente_nome = matricola_to_name.get(str(richiesta['Ricevente_Matricola']), "Sconosciuto")
            st.markdown(f"- Richiesta inviata a **{ricevente_nome}** per il turno **{richiesta['ID_Turno']}**.")
