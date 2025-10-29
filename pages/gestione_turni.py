import streamlit as st
import pandas as pd
import datetime

# Importa le funzioni logiche necessarie dai moduli
from modules.shift_management import (
    prenota_turno_logic,
    cancella_prenotazione_logic,
    richiedi_sostituzione_logic,
    rispondi_sostituzione_logic,
    pubblica_turno_in_bacheca_logic,
    prendi_turno_da_bacheca_logic
)
from modules.data_manager import salva_gestionale_async
from modules.db_manager import get_shifts_by_type

# Mantieni questa funzione all'interno del modulo per coerenza
def render_turni_list(df_turni, gestionale, matricola_utente, ruolo, key_suffix):
    """
    Renderizza una lista di turni, con la logica per la prenotazione, cancellazione e sostituzione.
    """
    if df_turni.empty:
        st.info("Nessun turno di questo tipo disponibile al momento.")
        return

    mostra_solo_disponibili = st.checkbox("Mostra solo turni con posti disponibili", key=f"filter_turni_{key_suffix}")

    if ruolo == "Amministratore":
        search_term_turni = st.text_input("Cerca per descrizione del turno...", key=f"search_turni_{key_suffix}")
        if search_term_turni:
            df_turni = df_turni[df_turni['Descrizione'].str.contains(search_term_turni, case=False, na=False)]

    st.divider()

    if df_turni.empty:
        st.info("Nessun turno corrisponde alla ricerca.")

    for index, turno in df_turni.iterrows():
        prenotazioni_turno = gestionale['prenotazioni'][gestionale['prenotazioni']['ID_Turno'] == turno['ID_Turno']]
        posti_tecnico = int(turno['PostiTecnico'])
        posti_aiutante = int(turno['PostiAiutante'])
        tecnici_prenotati = len(prenotazioni_turno[prenotazioni_turno['RuoloOccupato'] == 'Tecnico'])
        aiutanti_prenotati = len(prenotazioni_turno[prenotazioni_turno['RuoloOccupato'] == 'Aiutante'])

        is_available = (tecnici_prenotati < posti_tecnico) or (aiutanti_prenotati < posti_aiutante)
        if mostra_solo_disponibili and not is_available:
            continue

        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown(f"**{turno['Descrizione']}**")
        st.caption(f"{pd.to_datetime(turno['Data']).strftime('%d/%m/%Y')} | {turno['OrarioInizio']} - {turno['OrarioFine']}")

        tech_icon = "✅" if tecnici_prenotati < posti_tecnico else "❌"
        aiut_icon = "✅" if aiutanti_prenotati < posti_aiutante else "❌"
        st.markdown(f"**Posti:** `Tecnici: {tecnici_prenotati}/{posti_tecnico}` {tech_icon} | `Aiutanti: {aiutanti_prenotati}/{posti_aiutante}` {aiut_icon}")

        if not prenotazioni_turno.empty:
            st.markdown("**Personale Prenotato:**")
            df_contatti = gestionale.get('contatti', pd.DataFrame())
            matricola_to_name = pd.Series(df_contatti['Nome Cognome'].values, index=df_contatti['Matricola'].astype(str)).to_dict()

            for _, p in prenotazioni_turno.iterrows():
                matricola = str(p['Matricola'])
                nome_utente = matricola_to_name.get(matricola, f"Matricola {matricola}")
                ruolo_utente_turno = p['RuoloOccupato']

                user_details = df_contatti[df_contatti['Matricola'] == matricola]
                is_placeholder = user_details.empty or pd.isna(user_details.iloc[0].get('PasswordHash'))

                display_name = f"*{nome_utente} (Esterno)*" if is_placeholder else nome_utente
                st.markdown(f"- {display_name} (*{ruolo_utente_turno}*)", unsafe_allow_html=True)

        st.markdown("---")

        if ruolo == "Amministratore":
            if st.button("✏️ Modifica Turno", key=f"edit_{turno['ID_Turno']}_{key_suffix}"):
                st.session_state['editing_turno_id'] = turno['ID_Turno']
                st.rerun()
            st.markdown("---")

        prenotazione_utente = prenotazioni_turno[prenotazioni_turno['Matricola'] == str(matricola_utente)]

        if not prenotazione_utente.empty:
            st.success("Sei prenotato per questo turno.")

            if 'confirm_action' not in st.session_state:
                st.session_state.confirm_action = None

            is_confirmation_pending = st.session_state.confirm_action and st.session_state.confirm_action.get('turno_id') == turno['ID_Turno']

            if is_confirmation_pending:
                action_type = st.session_state.confirm_action['type']
                if action_type == 'cancel':
                    st.warning("❓ Sei sicuro di voler cancellare la tua prenotazione?")
                elif action_type == 'publish':
                    st.warning("❓ Sei sicuro di voler pubblicare il tuo turno in bacheca?")

                col_yes, col_no, col_spacer = st.columns([1, 1, 2])
                with col_yes:
                    if st.button("✅ Sì", key=f"confirm_yes_{turno['ID_Turno']}", width='stretch'):
                        success = False
                        if action_type == 'cancel':
                            if cancella_prenotazione_logic(gestionale, matricola_utente, turno['ID_Turno']):
                                success = True
                        elif action_type == 'publish':
                            if pubblica_turno_in_bacheca_logic(gestionale, matricola_utente, turno['ID_Turno']):
                                success = True

                        if success:
                            salva_gestionale_async(gestionale)

                        st.session_state.confirm_action = None
                        st.rerun()
                with col_no:
                    if st.button("❌ No", key=f"confirm_no_{turno['ID_Turno']}", width='stretch'):
                        st.session_state.confirm_action = None
                        st.rerun()
            else:
                col1, col2, col3 = st.columns(3)
                with col1:
                    if st.button("Cancella Prenotazione", key=f"del_{turno['ID_Turno']}_{key_suffix}", help="Rimuove la tua prenotazione dal turno."):
                        st.session_state.confirm_action = {'type': 'cancel', 'turno_id': turno['ID_Turno']}
                        st.rerun()
                with col2:
                    if st.button("📢 Pubblica in Bacheca", key=f"pub_{turno['ID_Turno']}_{key_suffix}", help="Rilascia il tuo turno e rendilo disponibile a tutti in bacheca."):
                        st.session_state.confirm_action = {'type': 'publish', 'turno_id': turno['ID_Turno']}
                        st.rerun()
                with col3:
                    if st.button("🔄 Chiedi Sostituzione", key=f"ask_{turno['ID_Turno']}_{key_suffix}", help="Chiedi a un collega specifico di sostituirti."):
                        st.session_state['sostituzione_turno_id'] = turno['ID_Turno']
                        st.rerun()
        else:
            opzioni = []
            if tecnici_prenotati < posti_tecnico: opzioni.append("Tecnico")
            if aiutanti_prenotati < posti_aiutante: opzioni.append("Aiutante")
            if opzioni:
                ruolo_scelto = st.selectbox("Prenota come:", opzioni, key=f"sel_{turno['ID_Turno']}_{key_suffix}")
                if st.button("Conferma Prenotazione", key=f"add_{turno['ID_Turno']}_{key_suffix}"):
                    if prenota_turno_logic(gestionale, matricola_utente, turno['ID_Turno'], ruolo_scelto):
                        salva_gestionale_async(gestionale); st.rerun()
            else:
                st.warning("Turno al completo.")
                if st.button("Chiedi Sostituzione", key=f"ask_full_{turno['ID_Turno']}_{key_suffix}"):
                    st.session_state['sostituzione_turno_id'] = turno['ID_Turno']; st.rerun()

        if st.session_state.get('sostituzione_turno_id') == turno['ID_Turno']:
            st.markdown("---")
            st.markdown("**A chi vuoi chiedere il cambio?**")

            matricola_to_name = pd.Series(gestionale['contatti']['Nome Cognome'].values, index=gestionale['contatti']['Matricola'].astype(str)).to_dict()

            if not prenotazione_utente.empty:
                ricevente_options = prenotazioni_turno['Matricola'].tolist()
            else:
                ricevente_options = gestionale['contatti']['Matricola'].tolist()

            ricevente_options = [str(m) for m in ricevente_options if str(m) != str(matricola_utente)]

            ricevente_matricola = st.selectbox("Seleziona collega:", ricevente_options, format_func=lambda m: matricola_to_name.get(m, m), key=f"swap_select_{turno['ID_Turno']}_{key_suffix}")

            if st.button("Invia Richiesta", key=f"swap_confirm_{turno['ID_Turno']}_{key_suffix}"):
                if richiedi_sostituzione_logic(gestionale, matricola_utente, ricevente_matricola, turno['ID_Turno']):
                    salva_gestionale_async(gestionale); del st.session_state['sostituzione_turno_id']; st.rerun()

        st.markdown('</div>', unsafe_allow_html=True)

def render_reperibilita_tab(gestionale_data, matricola_utente, ruolo_utente):
    st.subheader("📅 Calendario Reperibilità Settimanale")

    HOLIDAYS_2025 = [
        datetime.date(2025, 1, 1), datetime.date(2025, 1, 6), datetime.date(2025, 4, 20),
        datetime.date(2025, 4, 21), datetime.date(2025, 4, 25), datetime.date(2025, 5, 1),
        datetime.date(2025, 6, 2), datetime.date(2025, 8, 15), datetime.date(2025, 11, 1),
        datetime.date(2025, 12, 8), datetime.date(2025, 12, 25), datetime.date(2025, 12, 26),
    ]
    WEEKDAY_NAMES_IT = ["Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"]
    MESI_ITALIANI = ["Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno", "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"]
    today = datetime.date.today()

    if 'managing_oncall_shift_id' in st.session_state and st.session_state.managing_oncall_shift_id:
        shift_id_to_manage = st.session_state.managing_oncall_shift_id
        matricola_to_manage = st.session_state.managing_oncall_user_matricola
        df_contatti = gestionale_data['contatti']
        user_to_manage_name = df_contatti[df_contatti['Matricola'] == matricola_to_manage].iloc[0]['Nome Cognome']

        with st.container(border=True):
            st.subheader("Gestione Turno di Reperibilità")
            try:
                turno_info = gestionale_data['turni'][gestionale_data['turni']['ID_Turno'] == shift_id_to_manage].iloc[0]
                st.write(f"Stai modificando il turno di **{user_to_manage_name}** per il giorno **{pd.to_datetime(turno_info['Data']).strftime('%d/%m/%Y')}**.")
            except IndexError:
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
                with c1:
                    if st.button("Invia Richiesta", key=f"swap_confirm_{shift_id_to_manage}", width='stretch', type="primary"):
                        if richiedi_sostituzione_logic(gestionale_data, matricola_to_manage, ricevente_matricola, shift_id_to_manage):
                            salva_gestionale_async(gestionale_data)
                            del st.session_state.managing_oncall_shift_id
                            if 'oncall_swap_mode' in st.session_state: del st.session_state.oncall_swap_mode
                            st.rerun()
                with c2:
                    if st.button("Annulla Scambio", width='stretch'):
                        del st.session_state.oncall_swap_mode
                        st.rerun()
            else:
                st.info("Cosa vuoi fare con questo turno?")
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("📢 Pubblica in Bacheca", width='stretch'):
                        if pubblica_turno_in_bacheca_logic(gestionale_data, matricola_to_manage, shift_id_to_manage):
                            salva_gestionale_async(gestionale_data)
                            del st.session_state.managing_oncall_shift_id
                            st.rerun()
                with col2:
                    if st.button("🔄 Chiedi Sostituzione", width='stretch'):
                        st.session_state.oncall_swap_mode = True
                        st.rerun()

            st.divider()
            if st.button("⬅️ Torna al Calendario", key=f"cancel_manage_{shift_id_to_manage}", width='stretch'):
                if 'managing_oncall_shift_id' in st.session_state: del st.session_state.managing_oncall_shift_id
                if 'managing_oncall_user_matricola' in st.session_state: del st.session_state.managing_oncall_user_matricola
                if 'oncall_swap_mode' in st.session_state: del st.session_state.oncall_swap_mode
                st.rerun()
        st.stop()

    if 'week_start_date' not in st.session_state:
        st.session_state.week_start_date = today - datetime.timedelta(days=today.weekday())

    current_year = st.session_state.week_start_date.year
    selected_month = st.selectbox(
        "Mese", range(1, 13),
        format_func=lambda m: MESI_ITALIANI[m-1],
        index=st.session_state.week_start_date.month - 1,
        key="month_select"
    )
    selected_year = st.selectbox(
        "Anno", range(2024, 2027),
        index=current_year - 2024,
        key="year_select"
    )

    if selected_year != st.session_state.week_start_date.year or selected_month != st.session_state.week_start_date.month:
        new_date = datetime.date(selected_year, selected_month, 1)
        st.session_state.week_start_date = new_date - datetime.timedelta(days=new_date.weekday())
        st.rerun()

    col_nav1, col_nav2, col_nav3 = st.columns([1, 5, 1])
    with col_nav1:
        if st.button("⬅️", help="Settimana precedente", width='stretch'):
            st.session_state.week_start_date -= datetime.timedelta(weeks=1)
            st.rerun()
    with col_nav2:
        week_start = st.session_state.week_start_date
        week_end = week_start + datetime.timedelta(days=6)
        week_label = f"{week_start.strftime('%d')} {MESI_ITALIANI[week_start.month-1]}"
        if week_start.year != week_end.year:
            week_label += f" {week_start.year} — {week_end.strftime('%d')} {MESI_ITALIANI[week_end.month-1]} {week_end.year}"
        elif week_start.month != week_end.month:
            week_label += f" — {week_end.strftime('%d')} {MESI_ITALIANI[week_end.month-1]} {week_end.year}"
        else:
            week_label += f" — {week_end.strftime('%d')} {MESI_ITALIANI[week_end.month-1]} {week_end.year}"
        st.markdown(f"<div style='text-align: center; font-weight: bold; margin-top: 8px;'>{week_label}</div>", unsafe_allow_html=True)
    with col_nav3:
        if st.button("➡️", help="Settimana successiva", width='stretch'):
            st.session_state.week_start_date += datetime.timedelta(weeks=1)
            st.rerun()

    if st.button("Vai a Oggi", width='stretch'):
        st.session_state.week_start_date = today - datetime.timedelta(days=today.weekday())
        st.rerun()

    st.divider()

    df_turni = gestionale_data['turni']
    df_prenotazioni = gestionale_data['prenotazioni']
    oncall_shifts_df = df_turni[df_turni['Tipo'] == 'Reperibilità'].copy()
    oncall_shifts_df['Data'] = pd.to_datetime(oncall_shifts_df['Data'])
    oncall_shifts_df['date_only'] = oncall_shifts_df['Data'].dt.date

    week_dates = [st.session_state.week_start_date + datetime.timedelta(days=i) for i in range(7)]
    cols = st.columns(7)

    for i, day in enumerate(week_dates):
        with cols[i]:
            is_today = (day == today)
            is_weekend = day.weekday() in [5, 6]
            is_holiday = day in HOLIDAYS_2025
            border_style = "2px solid #007bff" if is_today else "1px solid #d3d3d3"
            day_color = "red" if is_holiday else "inherit"
            background_color = "#e0f7fa" if is_today else ("#fff0f0" if is_weekend else "white")

            technicians_html = ""
            shift_today = oncall_shifts_df[oncall_shifts_df['date_only'] == day]
            user_is_on_call = False
            shift_id_today = None
            managed_user_matricola = matricola_utente

            if not shift_today.empty:
                shift_id_today = shift_today.iloc[0]['ID_Turno']
                prenotazioni_today = df_prenotazioni[df_prenotazioni['ID_Turno'] == shift_id_today]
                df_contatti = gestionale_data.get('contatti', pd.DataFrame())
                matricola_to_name = pd.Series(df_contatti['Nome Cognome'].values, index=df_contatti['Matricola'].astype(str)).to_dict()

                if not prenotazioni_today.empty:
                    tech_display_list = []
                    for _, booking in prenotazioni_today.iterrows():
                        technician_matricola = str(booking['Matricola'])
                        technician_name = matricola_to_name.get(technician_matricola, f"Matricola {technician_matricola}")
                        surname = technician_name.split()[-1].upper()
                        user_details = df_contatti[df_contatti['Matricola'] == technician_matricola]
                        is_placeholder = user_details.empty or pd.isna(user_details.iloc[0].get('PasswordHash'))
                        display_name = f"<i>{surname} (Esterno)</i>" if is_placeholder else surname
                        tech_display_list.append(display_name)
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
                if st.button("Gestisci", key=f"manage_{day}", width='stretch'):
                    st.session_state.managing_oncall_shift_id = shift_id_today
                    st.session_state.managing_oncall_user_matricola = managed_user_matricola
                    st.rerun()

def render_gestione_turni_tab(gestionale_data, matricola_utente, ruolo):
    """
    Funzione principale che renderizza l'intera scheda "Gestione Turni".
    """
    st.subheader("Gestione Turni")
    turni_disponibili_tab, bacheca_tab, sostituzioni_tab = st.tabs(["📅 Turni", "📢 Bacheca", "🔄 Sostituzioni"])

    with turni_disponibili_tab:
        assistenza_tab, straordinario_tab, reperibilita_tab = st.tabs(["Turni Assistenza", "Turni Straordinario", "Turni Reperibilità"])
        with assistenza_tab:
            df_assistenza = get_shifts_by_type('Assistenza')
            render_turni_list(df_assistenza, gestionale_data, matricola_utente, ruolo, "assistenza")
        with straordinario_tab:
            df_straordinario = get_shifts_by_type('Straordinario')
            render_turni_list(df_straordinario, gestionale_data, matricola_utente, ruolo, "straordinario")
        with reperibilita_tab:
            render_reperibilita_tab(gestionale_data, matricola_utente, ruolo)

    with bacheca_tab:
        st.subheader("Turni Liberi in Bacheca")
        df_bacheca = gestionale_data.get('bacheca', pd.DataFrame())
        turni_disponibili_bacheca = df_bacheca[df_bacheca['Stato'] == 'Disponibile'].sort_values(by='Timestamp_Pubblicazione', ascending=False)
        if turni_disponibili_bacheca.empty:
            st.info("Al momento non ci sono turni liberi in bacheca.")
        else:
            df_turni = gestionale_data['turni']
            matricola_to_name = pd.Series(gestionale_data['contatti']['Nome Cognome'].values, index=gestionale_data['contatti']['Matricola'].astype(str)).to_dict()
            for _, bacheca_entry in turni_disponibili_bacheca.iterrows():
                try:
                    turno_details = df_turni[df_turni['ID_Turno'] == bacheca_entry['ID_Turno']].iloc[0]
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
                                if prendi_turno_da_bacheca_logic(gestionale_data, matricola_utente, ruolo, bacheca_entry['ID_Bacheca']):
                                    salva_gestionale_async(gestionale_data)
                                    st.rerun()
                        else:
                            st.info("Non hai il ruolo richiesto per questo turno.")
                except IndexError:
                    st.warning(f"Dettagli non trovati per il turno ID {bacheca_entry['ID_Turno']}. Potrebbe essere stato rimosso.")

    with sostituzioni_tab:
        st.subheader("Richieste di Sostituzione")
        df_sostituzioni = gestionale_data['sostituzioni']
        matricola_to_name = pd.Series(gestionale_data['contatti']['Nome Cognome'].values, index=gestionale_data['contatti']['Matricola'].astype(str)).to_dict()
        st.markdown("#### 📥 Richieste Ricevute")
        richieste_ricevute = df_sostituzioni[df_sostituzioni['Ricevente_Matricola'] == str(matricola_utente)]
        if richieste_ricevute.empty:
            st.info("Nessuna richiesta di sostituzione ricevuta.")
        for _, richiesta in richieste_ricevute.iterrows():
            with st.container(border=True):
                richiedente_nome = matricola_to_name.get(str(richiesta['Richiedente_Matricola']), "Sconosciuto")
                st.markdown(f"**{richiedente_nome}** ti ha chiesto un cambio per il turno **{richiesta['ID_Turno']}**.")
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("✅ Accetta", key=f"acc_{richiesta['ID_Richiesta']}"):
                        if rispondi_sostituzione_logic(gestionale_data, richiesta['ID_Richiesta'], matricola_utente, True):
                            salva_gestionale_async(gestionale_data)
                            st.rerun()
                with c2:
                    if st.button("❌ Rifiuta", key=f"rif_{richiesta['ID_Richiesta']}"):
                        if rispondi_sostituzione_logic(gestionale_data, richiesta['ID_Richiesta'], matricola_utente, False):
                            salva_gestionale_async(gestionale_data)
                            st.rerun()
        st.divider()
        st.markdown("#### 📤 Richieste Inviate")
        richieste_inviate = df_sostituzioni[df_sostituzioni['Richiedente_Matricola'] == str(matricola_utente)]
        if richieste_inviate.empty:
            st.info("Nessuna richiesta di sostituzione inviata.")
        for _, richiesta in richieste_inviate.iterrows():
            ricevente_nome = matricola_to_name.get(str(richiesta['Ricevente_Matricola']), "Sconosciuto")
            st.markdown(f"- Richiesta inviata a **{ricevente_nome}** per il turno **{richiesta['ID_Turno']}**.")
