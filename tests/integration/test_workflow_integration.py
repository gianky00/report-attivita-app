
import unittest
import sys
import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

# Add root and src to path
root_dir = Path(__file__).parent.parent.parent
sys.path.append(str(root_dir))
sys.path.append(str(root_dir / "src"))

from app import main_app
from modules import session_manager
from tests.unit.modules.st_mock_helper import MockSessionState

class TestWorkflowIntegration(unittest.TestCase):
    
    def setUp(self):
        # Mock Session State using MockSessionState wrapper
        self.state_dict = {
            "user": {"Username": "U1", "Ruolo": "Tecnico", "Nome Cognome": "Mario Rossi"},
            "logged_in": True,
            "page": "Report",
            "main_tab": "Attività Assegnate", # Default tab for technicians
            "navigated": False
        }
        self.session_state = MockSessionState(self.state_dict)
        
        self.patcher_st = patch('app.st')
        self.mock_st = self.patcher_st.start()
        self.mock_st.session_state = self.session_state
        
        # Determine column mocking strategy
        def columns_side_effect(spec, *args, **kwargs):
             count = spec if isinstance(spec, int) else len(spec)
             cols = [MagicMock() for _ in range(count)]
             for i, c in enumerate(cols): 
                 c.__enter__.return_value = c
                 # First column = Submit (True), Second = Cancel (False)
                 if i == 0:
                    c.button.return_value = True
                 else:
                    c.button.return_value = False
             return cols
        self.mock_st.columns.side_effect = columns_side_effect

        # Mock page config to avoid errors
        self.mock_st.set_page_config = MagicMock()

        # Mock other critical components
        self.patcher_db = patch('modules.db_manager.get_db_connection')
        self.mock_db_conn = self.patcher_db.start()
        
        # Setup sidebar mock
        self.mock_st.sidebar.selectbox.return_value = "Report"

    def tearDown(self):
        self.patcher_st.stop()
        self.patcher_db.stop()

    @patch('app.get_user_by_matricola')
    @patch('components.forms.debriefing_form.scrivi_o_aggiorna_risposta')
    @patch('components.ui.activity_ui.get_unvalidated_reports_by_technician')
    @patch('modules.data_manager.carica_knowledge_core')
    @patch('components.forms.debriefing_form.st')
    def test_workflow_login_to_report_submission(self, mock_form_st, mock_load_knowledge, mock_get_reports, mock_save_report, mock_get_user):
        """
        Simulates:
        1. User is logged in (setup)
        2. Navigates to Report page (implied by call to render sidebar logic)
        3. Sees activity list
        4. Submits a report
        """
        # Connect mocks
        mock_form_st.session_state = self.session_state
        mock_form_st.write = MagicMock()
        mock_form_st.error = MagicMock()
        mock_form_st.success = MagicMock()
        mock_form_st.columns.side_effect = self.mock_st.columns.side_effect # Use same logic for columns
        mock_load_knowledge.return_value = {"some": "knowledge"}

        # Setup data
        mock_get_reports.return_value = [
            {"id": "1", "descrizione": "Activity 1", "stato": "Da Completare"}
        ]
        mock_save_report.return_value = True
        mock_get_user.return_value = {"Nome Cognome": "Mario Rossi", "Ruolo": "Tecnico"}
        
        # Mock UI interactions
        # Input for the form in debriefing_form.py
        # It likely uses st.text_area, st.selectbox etc.
        mock_form_st.text_area.return_value = "Work done."
        mock_form_st.selectbox.return_value = "Completato"
        mock_form_st.button.return_value = True 
        
        self.mock_st.button.return_value = True # For any buttons in main app if any

        # Trigger debriefing UI
        self.session_state["debriefing_task"] = {
            "id": 1, 
            "data_attivita": datetime.date.today(),
            "pdl": "PDL-XYZ",
            "attivita": "Manutenzione",
            "section_key": "today"
        }
        
        # Execute Main App Logic
        with patch('app.render_sidebar') as mock_sidebar:
             with patch('components.ui.navigation_ui.render_sidebar') as mock_nav_sidebar:
                # We do NOT patch render_debriefing_ui anymore, we want to run it!
                # with patch('components.forms.debriefing_form.render_debriefing_ui') as mock_render_form:
                    # Mock open for CSS loading
                    with patch('builtins.open', mock_open(read_data="css {}")):
                        # Run app
                        user = self.session_state["user"]
                        main_app(user["Username"], user["Ruolo"])
                        
                        # Verify save report was called
                        # 'scrivi_o_aggiorna_risposta' should be called
                        mock_save_report.assert_called()

    @patch('pages.gestione_turni.get_all_bookings')
    @patch('pages.gestione_turni.get_all_users')
    @patch('pages.gestione_turni.get_all_bacheca_items')
    @patch('pages.gestione_turni.get_all_substitutions')
    @patch('pages.gestione_turni.get_shifts_by_type')
    @patch('pages.shifts.oncall_calendar_view.get_shifts_by_type')
    @patch('app.get_user_by_matricola')
    @patch('pages.gestione_turni.st')
    @patch('pages.shifts.oncall_calendar_view.st')
    def test_admin_workflow_manage_shifts(self, mock_cal_st, mock_gt_st, mock_get_user, mock_get_shifts_view, mock_get_shifts_gt, mock_get_subs, mock_get_bacheca, mock_get_users, mock_get_bookings):
        """
        Simulates:
        1. Admin Logs in
        2. Navigates to 'Gestione Turni'
        3. Opens 'Reperibilità' tab
        4. Clicks 'Edit' on a shift
        5. Verify edit form is rendered
        """
        import pandas as pd
        
        # Link mock STs to main mock ST to share configuration
        mock_gt_st.session_state = self.session_state
        mock_gt_st.tabs.side_effect = self.mock_st.tabs.side_effect
        
        mock_cal_st.session_state = self.session_state
        mock_cal_st.columns.side_effect = self.mock_st.columns.side_effect
        mock_cal_st.button.side_effect = self.mock_st.button.side_effect
        mock_cal_st.rerun = MagicMock()
        
        # Setup Admin Session
        self.session_state["user"] = {"Username": "ADM1", "Ruolo": "Amministratore", "Nome Cognome": "Admin User"}
        self.session_state["logged_in"] = True
        self.session_state["page"] = "Gestione Turni" # Implicit via sidebar selection
        
        # Mock Data
        mock_get_user.return_value = {"Nome Cognome": "Admin User", "Ruolo": "Amministratore"}
        mock_get_users.return_value = pd.DataFrame([
            {"Matricola": "U1", "Nome Cognome": "Mario Rossi"},
            {"Matricola": "ADM1", "Nome Cognome": "Admin User"}
        ])
        mock_get_bookings.return_value = pd.DataFrame([
            {"ID_Turno": "S1", "Matricola": "U1", "Data": datetime.date.today()}
        ])
        # Assign columns to avoid KeyError when accessing empty DFs
        mock_get_shifts_gt.return_value = pd.DataFrame(columns=["ID_Turno", "Data", "Tipo", "Stato"]) 
        
        # For Calendar View
        today = datetime.date.today()
        mock_get_shifts_view.return_value = pd.DataFrame([
             {"ID_Turno": "S1", "Data": today, "Tipo": "Reperibilità", "Stato": "Confermato"}
        ])
        
        mock_get_bacheca.return_value = pd.DataFrame(columns=[
            "Stato", "Data", "Tipo", "Timestamp_Pubblicazione", "Richiedente", "ID_Turno",
            "Ricevente_Matricola", "Motivazione", "Richiedente_Matricola", "Note"
        ])
        mock_get_subs.return_value = pd.DataFrame(columns=[
            "Stato", "Data", "Tipo", "Richiedente", "Sostituto", "ID_Turno",
            "Ricevente_Matricola", "Motivazione", "Richiedente_Matricola", "Sostituto_Matricola", "Note"
        ])
        
        # KEY FIX: Set main_tab explicitly since render_sidebar is patched
        self.session_state["main_tab"] = "Gestione Turni"

        # Mock Sidebar to select 'Gestione Turni'
        self.mock_st.sidebar.selectbox.return_value = "Gestione Turni"
        
        # Mock Tabs in Gestione Turni (Turni, Bacheca, Sostituzioni)
        # We need to simulate entering the first tab "Turni"
        # Then inside "Turni", entering the third tab "Reperibilità"
        
        # We can use side_effect for st.tabs to return mocks that we can enter
        # But our MockSessionState + patcher_st might handle it if we configured it right.
        # Let's refine the columns/tabs mock if needed.
        
        # Reuse column strategy
        def tabs_side_effect(spec, *args, **kwargs):
             count = spec if isinstance(spec, int) else len(spec)
             tabs = [MagicMock() for _ in range(count)]
             for t in tabs: t.__enter__.return_value = t
             return tabs
        self.mock_st.tabs.side_effect = tabs_side_effect
        mock_gt_st.tabs.side_effect = tabs_side_effect

        # Custom column strategy for Admin Test
        def admin_columns_side_effect(spec, *args, **kwargs):
             count = spec if isinstance(spec, int) else len(spec)
             cols = [MagicMock() for _ in range(count)]
             for i, c in enumerate(cols): 
                 c.__enter__.return_value = c
                 
                 # Define button side effect
                 def btn_se(*args, **kwargs):
                     if i == 1: return True
                     return False
                 
                 c.button.side_effect = btn_se
                 
             return cols
        self.mock_st.columns.side_effect = admin_columns_side_effect
        mock_cal_st.columns.side_effect = admin_columns_side_effect
        
        # We need to target the SPECIFIC button that corresponds to the edit action
        # In _render_day_cell: if c2.button(..., key=f"e_{day}")
        # We need to ensure that specific button returns True.
        
        target_key = f"e_{today}"
        
        def button_side_effect(label=None, key=None, **kwargs):
            if key == target_key:
                return True
            return False
            
        self.mock_st.button.side_effect = button_side_effect
        
        # Execute
        with patch('app.render_sidebar'):
            with patch('components.ui.navigation_ui.render_sidebar'):
                 with patch('builtins.open', mock_open(read_data="css {}")):
                    
                    user = self.session_state["user"]
                    main_app(user["Username"], user["Ruolo"])
                    
                    # Verify that session state has 'editing_oncall_shift_id' set
                    # The button click sets it to "S1"
                    self.assertIn("editing_oncall_shift_id", self.session_state)
                    self.assertEqual(self.session_state["editing_oncall_shift_id"], "S1")
