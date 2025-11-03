import streamlit as st
import datetime
from modules.data_manager import trova_attivita, _carica_giornaliera_mese, carica_knowledge_core
from modules.db_manager import get_all_users, get_validated_intervention_reports, count_unread_notifications, get_last_login, get_user_by_matricola
from modules.oncall_logic import get_next_on_call_week
from modules.shift_management import sync_oncall_shifts
from learning_module import get_report_knowledge_base_count
from modules.instrumentation_logic import get_technical_suggestions, find_and_analyze_tags, analyze_domain_terminology
from modules.db_manager import salva_relazione
import google.generativeai as genai
from modules.email_sender import invia_email_con_outlook_async
from modules.notifications import leggi_notifiche
from components.ui_components import disegna_sezione_attivita, render_notification_center
from components.form_handlers import render_edit_shift_form, render_debriefing_ui
from pages.gestione_turni import render_gestione_turni_tab
from pages.richieste import render_richieste_tab
from pages.admin import render_caposquadra_view, render_sistema_view
from pages.guida import render_guida_tab
from pages.storico import render_storico_tab
from modules.session_manager import delete_session
import pandas as pd

def recupera_attivita_non_rendicontate(matricola_utente, df_contatti):
    """
    Recupera le attività non rendicontate degli ultimi 30 giorni.
    """
    oggi = datetime.date.today()
    attivita_da_recuperare = []
    for i in range(1, 31):
        giorno_controllo = oggi - datetime.timedelta(days=i)
        attivita_giorno = trova_attivita(matricola_utente, giorno_controllo.day, giorno_controllo.month, giorno_controllo.year, df_contatti)
        for task in attivita_giorno:
            task['data_attivita'] = giorno_controllo
        attivita_da_recuperare.extend(attivita_giorno)
    return attivita_da_recuperare

def revisiona_relazione_con_ia(_testo_originale, _knowledge_base):
    """
    Usa l'IA per revisionare una relazione tecnica, arricchendo la richiesta
    con analisi semantica della strumentazione basata su standard ISA S5.1.
    """
    # Funzione mantenuta per la revisione delle relazioni, ma non più per i report
    GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY")
    if not GEMINI_API_KEY:
        return {"error": "La chiave API di Gemini non è configurata."}
    if not _testo_originale.strip():
        return {"info": "Il testo della relazione è vuoto."}

    # 1. Analisi semantica della strumentazione e della terminologia
    loops, analyzed_tags = find_and_analyze_tags(_testo_originale)
    domain_terms = analyze_domain_terminology(_testo_originale)

    technical_summary = ""
    if loops:
        technical_summary += "Analisi del Contesto Strumentale:\n"
        for loop_id, components in loops.items():
            main_variable = components[0]['variable']
            technical_summary += f"- Loop di Controllo {loop_id} ({main_variable}):\n"
            for comp in components:
                technical_summary += f"  - {comp['tag']}: È un {comp['type']} ({comp['description']}).\n"

            controller = next((c for c in components if c['type'] == '[CONTROLLORE]'), None)
            actuator = next((c for c in components if c['type'] == '[ATUTTATORE]'), None)
            if controller and actuator:
                technical_summary += f"  - Relazione: Il controllore {controller['tag']} comanda l'attuatore {actuator['tag']}.\n"
        technical_summary += "\n"

    if domain_terms:
        technical_summary += "Terminologia Specifica Rilevata:\n"
        for term, definition in domain_terms.items():
            technical_summary += f"- {term.upper()}: {definition}.\n"
        technical_summary += "\n"

    # 2. Costruzione del prompt per l'IA
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('models/gemini-flash-latest')

        if technical_summary:
            prompt = f"""
            Sei un Direttore Tecnico di Manutenzione con profonda conoscenza della strumentazione (standard ISA S5.1) e della terminologia di impianto. Il tuo compito è riformulare la seguente relazione scritta da un tecnico, trasformandola in un report professionale, chiaro e tecnicamente consapevole.
            **INFORMAZIONI TECNICHE E TERMINOLOGICHE DA USARE (Know-How):**
            ---
            {technical_summary}
            ---
            Usa queste informazioni per interpretare correttamente le sigle (es. CTG, FCV301) e le relazioni tra i componenti. Riformula il testo per riflettere questa comprensione approfondita.
            **RELAZIONE ORIGINALE DA RIFORMULARE:**
            ---
            {_testo_originale}
            ---
            **RELAZIONE RIFORMULATA (restituisci solo il testo corretto, senza aggiungere titoli o commenti):**
            """
        else:
            prompt = f"""
            Sei un revisore esperto di relazioni tecniche in ambito industriale. Il tuo compito è revisionare e migliorare il seguente testo scritto da un tecnico, mantenendo un tono professionale, chiaro e conciso. Correggi eventuali errori grammaticali o di battitura.
            **RELAZIONE DA REVISIONARE:**
            ---
            {_testo_originale}
            ---
            **RELAZIONE REVISIONATA (restituisci solo il testo corretto, senza aggiungere titoli o commenti):**
            """

        response = model.generate_content(prompt)
        return {"success": True, "text": response.text}
    except Exception as e:
        return {"error": f"Errore durante la revisione IA: {str(e)}"}

def main_app(matricola_utente, ruolo):
    st.set_page_config(layout="wide", page_title="Gestionale", initial_sidebar_state="collapsed")

    def load_css(file_name):
        with open(file_name) as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

    load_css('styles/style.css')

    user_info = get_user_by_matricola(matricola_utente)
    if user_info:
        nome_utente_autenticato = user_info['Nome Cognome']
    else:
        st.error("Errore critico: impossibile trovare i dati dell'utente loggato.")
        st.stop()

    today = datetime.date.today()
    # Estende il periodo di sincronizzazione a 1 anno per coprire un orizzonte più ampio
    start_sync_date = today - datetime.timedelta(days=180)
    end_sync_date = today + datetime.timedelta(days=180)

    if sync_oncall_shifts(start_date=start_sync_date, end_date=end_sync_date):
        st.toast("Calendario reperibilità sincronizzato.")

    if st.session_state.get('editing_turno_id'):
        render_edit_shift_form()
    elif st.session_state.get('debriefing_task'):
        knowledge_core = carica_knowledge_core()
        if knowledge_core:
            task_info = st.session_state.debriefing_task
            data_riferimento_attivita = task_info.get('data_attivita', datetime.date.today())
            render_debriefing_ui(knowledge_core, matricola_utente, data_riferimento_attivita)
    else:
        if 'drawer_open' not in st.session_state:
            st.session_state.drawer_open = False
        if 'main_tab' not in st.session_state:
            st.session_state.main_tab = "Attività Assegnate"
        if 'expanded_menu' not in st.session_state:
            st.session_state.expanded_menu = "Attività"

        # App Bar
        unread_notifications = count_unread_notifications(matricola_utente)
        st.title(st.session_state.main_tab)
        if unread_notifications > 0:
            st.markdown(f'<div class="notification-badge">{unread_notifications}</div>', unsafe_allow_html=True)

        # Sidebar Navigation
        with st.sidebar:
            st.header(f"Ciao, {nome_utente_autenticato}!")
            st.caption(f"Ruolo: {ruolo}")

            # Mostra la prossima settimana di reperibilità
            user_surname = nome_utente_autenticato.split()[-1]
            next_oncall_start = get_next_on_call_week(user_surname)
            if next_oncall_start:
                next_oncall_end = next_oncall_start + datetime.timedelta(days=6)
                today = datetime.date.today()

                # Controlla se oggi rientra nella settimana di reperibilità
                if next_oncall_start <= today <= next_oncall_end:
                    st.markdown("**Sei reperibile**")
                    message = f"Dal: {next_oncall_start.strftime('%d/%m')} al {next_oncall_end.strftime('%d/%m/%Y')}"
                else:
                    message = f"Prossima Reperibilità:\n{next_oncall_start.strftime('%d/%m')} - {next_oncall_end.strftime('%d/%m/%Y')}"

                st.info(message)

            user_notifications = leggi_notifiche(matricola_utente)
            render_notification_center(user_notifications, matricola_utente)

            last_login = get_last_login(matricola_utente)
            if last_login:
                last_login_dt = pd.to_datetime(last_login)
                st.caption(f"Ultimo accesso: {last_login_dt.strftime('%d/%m/%Y %H:%M')}")

            st.divider()

            # Top-level items
            if st.button("📝 Attività Assegnate", use_container_width=True):
                st.session_state.main_tab = "Attività Assegnate"
                st.session_state.navigated = True
                _carica_giornaliera_mese.clear()
                st.rerun()

            if st.button("🗂️ Storico", use_container_width=True):
                st.session_state.main_tab = "Storico"
                st.session_state.navigated = True
                st.rerun()

            st.divider()

            if st.button("📅 Gestione Turni", use_container_width=True):
                st.session_state.main_tab = "📅 Gestione Turni"
                st.session_state.navigated = True
                st.rerun()

            if st.button("Richieste", use_container_width=True):
                st.session_state.main_tab = "Richieste"
                st.session_state.navigated = True
                st.rerun()

            # Expandable sections
            expandable_menu_items = {}
            if ruolo == "Amministratore":
                expandable_menu_items["⚙️ Amministrazione"] = ["Caposquadra", "Sistema"]

            for main_item, sub_items in expandable_menu_items.items():
                is_expanded = main_item == st.session_state.expanded_menu

                if st.button(main_item, use_container_width=True):
                    st.session_state.expanded_menu = main_item if not is_expanded else ""
                    st.session_state.navigated = True
                    st.rerun()

                if is_expanded:
                    for sub_item in sub_items:
                        if st.button(sub_item, key=f"nav_{sub_item}", use_container_width=True):
                            st.session_state.main_tab = sub_item
                            st.session_state.navigated = True
                            st.rerun()

            st.divider()
            if st.button("❓ Guida", use_container_width=True):
                st.session_state.main_tab = "❓ Guida"
                st.session_state.navigated = True
                st.rerun()
            if st.button("Disconnetti", use_container_width=True):
                token_to_delete = st.session_state.get('session_token')
                delete_session(token_to_delete)
                keys_to_clear = [k for k in st.session_state.keys()]
                for key in keys_to_clear:
                    del st.session_state[key]
                st.query_params.clear()
                st.rerun()

        st.header(f"Ciao, {nome_utente_autenticato}!")
        st.caption(f"Ruolo: {ruolo}")

        st.markdown('<div class="main-container">', unsafe_allow_html=True)

        oggi = datetime.date.today()

        df_contatti = get_all_users()
        attivita_da_recuperare = recupera_attivita_non_rendicontate(matricola_utente, df_contatti)

        if 'main_tab' not in st.session_state:
            st.session_state.main_tab = "Attività Assegnate"

        main_tabs_list = ["Attività Assegnate", "📅 Gestione Turni", "Richieste", "Storico", "❓ Guida"]
        if ruolo == "Amministratore":
            if st.session_state.main_tab == "Caposquadra":
                render_caposquadra_view(matricola_utente)
                return  # Aggiunto per terminare l'esecuzione qui
            elif st.session_state.main_tab == "Sistema":
                render_sistema_view()
                return  # Aggiunto per terminare l'esecuzione qui
        selected_tab = st.session_state.main_tab

        st.markdown('<div class="page-content">', unsafe_allow_html=True)

        df_contatti = get_all_users()

        if selected_tab == "Attività Assegnate":
            sub_tab_list = ["Attività di Oggi", "Recupero Attività", "Attività Validate"]
            if ruolo in ["Tecnico", "Amministratore"]:
                sub_tab_list.append("Compila Relazione")
            sub_tabs = st.tabs(sub_tab_list)

            with sub_tabs[0]:
                st.subheader(f"Attività del {oggi.strftime('%d/%m/%Y')}")
                lista_attivita_raw = trova_attivita(matricola_utente, oggi.day, oggi.month, oggi.year, df_contatti)
                for task in lista_attivita_raw:
                    task['data_attivita'] = oggi
                disegna_sezione_attivita(lista_attivita_raw, "today", ruolo)

            with sub_tabs[1]:
                st.subheader("Recupero Attività Non Rendicontate (Ultimi 30 Giorni)")
                attivita_da_recuperare = recupera_attivita_non_rendicontate(matricola_utente, df_contatti)
                disegna_sezione_attivita(attivita_da_recuperare, "yesterday", ruolo)

            with sub_tabs[2]:
                st.subheader("Elenco Attività Validate")
                report_validati_df = get_validated_intervention_reports(matricola_tecnico=str(matricola_utente))
                if report_validati_df.empty:
                    st.info("Non hai ancora report validati.")
                else:
                    for _, report in report_validati_df.iterrows():
                        with st.expander(f"PdL `{report['pdl']}` - Intervento del {pd.to_datetime(report['data_riferimento_attivita']).strftime('%d/%m/%Y')}"):
                            st.markdown(f"**Descrizione:** {report['descrizione_attivita']}")
                            st.markdown(f"**Compilato il:** {pd.to_datetime(report['data_compilazione']).strftime('%d/%m/%Y %H:%M')}")
                            st.info(f"**Testo del Report:**\n\n{report['testo_report']}")
                            st.caption(f"ID Report: {report['id_report']} | Validato il: {pd.to_datetime(report['timestamp_validazione']).strftime('%d/%m/%Y %H:%M')}")

            # Contenuto per la nuova scheda "Compila Relazione"
            if ruolo in ["Tecnico", "Amministratore"] and len(sub_tabs) > 3:
                with sub_tabs[3]:
                    st.markdown('<div class="card">', unsafe_allow_html=True)
                    st.subheader("Compila Relazione di Reperibilità")

                    kb_count = get_report_knowledge_base_count()
                    if kb_count > 0:
                        st.caption(f"ℹ️ L'IA si basa su {kb_count} relazioni per la correzione.")
                    else:
                        st.caption("ℹ️ Base di conoscenza per l'IA non trovata o vuota.")

                    if 'relazione_testo' not in st.session_state: st.session_state.relazione_testo = ""
                    if 'relazione_partner' not in st.session_state: st.session_state.relazione_partner = None
                    if 'relazione_revisionata' not in st.session_state: st.session_state.relazione_revisionata = ""
                    if 'technical_suggestions' not in st.session_state: st.session_state.technical_suggestions = []

                    contatti_df = get_all_users()
                    lista_partner = contatti_df[contatti_df['Matricola'] != str(matricola_utente)]['Nome Cognome'].tolist()

                    with st.form("form_relazione"):
                        col_tech, col_partner = st.columns(2)
                        with col_tech: st.text_input("Tecnico Compilatore", value=nome_utente_autenticato, disabled=True)
                        with col_partner: partner_selezionato = st.selectbox("Seleziona Partner (opzionale)", options=["Nessuno"] + sorted(lista_partner), index=0)

                        c1, c2, c3 = st.columns(3)
                        data_intervento = c1.date_input("Data Intervento*", help="Questo campo è obbligatorio.")
                        ora_inizio = c2.text_input("Ora Inizio")
                        ora_fine = c3.text_input("Ora Fine")

                        st.session_state.relazione_testo = st.text_area("Corpo della Relazione", height=250, key="relazione_text_area", value=st.session_state.get('relazione_testo', ''))

                        b1, b2, b3 = st.columns(3)
                        submit_ai_button = b1.form_submit_button("🤖 Correggi con IA")
                        submit_suggestion_button = b2.form_submit_button("💡 Suggerimento Tecnico")
                        submit_save_button = b3.form_submit_button("✅ Invia Relazione", type="primary")

                    # Logica dopo la sottomissione del form, con formattazione corretta
                    if submit_ai_button:
                        testo_da_revisionare = st.session_state.get('relazione_text_area', '')
                        st.session_state.relazione_testo = testo_da_revisionare
                        if not testo_da_revisionare.strip():
                            st.warning("Per favore, scrivi il corpo della relazione prima di chiedere la correzione.")
                        elif not data_intervento:
                            st.error("Il campo 'Data Intervento' è obbligatorio.")
                        else:
                            with st.spinner("L'IA sta analizzando la relazione..."):
                                result = revisiona_relazione_con_ia(testo_da_revisionare, None)
                                if result.get("success"):
                                    st.session_state.relazione_revisionata = result["text"]
                                    st.success("Relazione corretta con successo!")
                                elif "error" in result:
                                    st.error(f"**Errore IA:** {result['error']}")
                                else:
                                    st.info(result.get("info", "Nessun suggerimento dall'IA."))

                    if submit_suggestion_button:
                        testo_per_suggerimenti = st.session_state.get('relazione_text_area', '')
                        if testo_per_suggerimenti.strip():
                            with st.spinner("Cerco suggerimenti tecnici..."):
                                suggestions = get_technical_suggestions(testo_per_suggerimenti)
                                st.session_state.technical_suggestions = suggestions
                                if not suggestions:
                                    st.toast("Nessun suggerimento specifico trovato per questo testo.")
                        else:
                            st.warning("Scrivi qualcosa nella relazione per ricevere suggerimenti.")

                    if submit_save_button:
                        testo_da_inviare = st.session_state.get('relazione_text_area', '')
                        if not data_intervento:
                            st.error("Il campo 'Data Intervento' è obbligatorio prima di inviare.")
                        elif not testo_da_inviare.strip():
                            st.error("Il corpo della relazione non può essere vuoto prima di inviare.")
                        else:
                            id_relazione = f"REL_{int(datetime.datetime.now().timestamp())}"
                            dati_nuova_relazione = {
                                "id_relazione": id_relazione,
                                "data_intervento": data_intervento.isoformat(),
                                "tecnico_compilatore": nome_utente_autenticato,
                                "partner": partner_selezionato if partner_selezionato != "Nessuno" else None,
                                "ora_inizio": ora_inizio,
                                "ora_fine": ora_fine,
                                "corpo_relazione": testo_da_inviare,
                                "stato": "Inviata",
                                "timestamp_invio": datetime.datetime.now().isoformat()
                            }

                            if salva_relazione(dati_nuova_relazione):
                                st.success("Relazione salvata e inviata con successo!")
                                partner_text = f" in coppia con {partner_selezionato}" if partner_selezionato != "Nessuno" else ""
                                titolo_email = f"Relazione di Reperibilità del {data_intervento.strftime('%d/%m/%Y')} - {nome_utente_autenticato}"

                                # Definisci il corpo dell'email separatamente per evitare problemi con f-string complesse
                                html_template = """
                                <html><head><style>body {{ font-family: Calibri, sans-serif; }}</style></head><body>
                                <h3>Relazione di Reperibilità</h3>
                                <p><strong>Data:</strong> {data_intervento}</p>
                                <p><strong>Tecnico:</strong> {nome_utente_autenticato}{partner_text}</p>
                                <p><strong>Orario:</strong> Da {ora_inizio} a {ora_fine}</p>
                                <hr>
                                <h4>Testo della Relazione:</h4>
                                <p>{testo_relazione}</p>
                                <br><hr>
                                <p><em>Email generata automaticamente dal sistema Gestionale.</em></p>
                                <p><strong>Gianky Allegretti</strong><br>Direttore Tecnico</p>
                                </body></html>
                                """
                                html_body = html_template.format(
                                    data_intervento=data_intervento.strftime('%d/%m/%Y'),
                                    nome_utente_autenticato=nome_utente_autenticato,
                                    partner_text=partner_text,
                                    ora_inizio=ora_inizio or 'N/D',
                                    ora_fine=ora_fine or 'N/D',
                                    testo_relazione=testo_da_inviare.replace('\n', '<br>')
                                )

                                invia_email_con_outlook_async(titolo_email, html_body)
                                st.balloons()
                                # Svuota i campi dopo l'invio
                                st.session_state.relazione_testo = ""
                                st.session_state.relazione_revisionata = ""
                                st.session_state.technical_suggestions = []
                                st.rerun()
                            else:
                                st.error("Errore durante il salvataggio della relazione nel database.")

                    if st.session_state.get('relazione_revisionata'):
                        st.subheader("Testo corretto dall'IA")
                        st.info(st.session_state.relazione_revisionata)
                        if st.button("📝 Usa Testo Corretto"):
                            st.session_state.relazione_testo = st.session_state.relazione_revisionata
                            st.session_state.relazione_revisionata = ""
                            st.rerun()

                    if st.session_state.get('technical_suggestions'):
                        st.subheader("💡 Suggerimenti Tecnici")
                        for suggestion in st.session_state.get('technical_suggestions', []):
                            st.info(suggestion)
                    st.markdown('</div>', unsafe_allow_html=True)
        elif selected_tab == "📅 Gestione Turni":
            render_gestione_turni_tab(matricola_utente, ruolo)
        elif selected_tab == "Richieste":
            render_richieste_tab(matricola_utente, ruolo, nome_utente_autenticato)
        elif selected_tab == "Storico":
            render_storico_tab()
        elif selected_tab == "❓ Guida":
            render_guida_tab(ruolo)

        st.markdown('</div>', unsafe_allow_html=True) # Close page-content
        st.markdown('</div>', unsafe_allow_html=True) # Close main-container
        st.markdown('</div>', unsafe_allow_html=True) # Close main-content

        if st.session_state.get('navigated'):
            st.components.v1.html("""
                <script>
                    setTimeout(() => {
                        window.parent.document.querySelector('[data-testid="stSidebar"] > div > div > button').click();
                    }, 100);
                </script>
            """, height=0)
            st.session_state.navigated = False

        st.markdown("""
            <script>
                const navLinks = window.parent.document.querySelectorAll(".nav-menu button");
                const pageContent = window.parent.document.querySelector(".page-content");

                navLinks.forEach(link => {
                    link.addEventListener("click", () => {
                        pageContent.classList.add("fade-out");
                        setTimeout(() => {
                        }, 200); // Corresponds to the CSS transition duration
                    });
                });
            </script>
        """, unsafe_allow_html=True)
