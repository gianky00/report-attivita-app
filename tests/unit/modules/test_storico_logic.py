import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd

# Add src to path
root_dir = Path(__file__).parent.parent.parent.parent
sys.path.append(str(root_dir / "src"))

from pages.storico import render_storico_tab


class TestStoricoLogic(unittest.TestCase):
    @patch("streamlit.tabs")
    @patch("streamlit.subheader")
    @patch("streamlit.text_input")
    @patch("streamlit.expander")
    @patch("streamlit.markdown")
    @patch("streamlit.text_area")
    @patch("pages.storico.get_validated_intervention_reports")
    @patch("pages.storico.get_validated_reports")
    @patch("pages.storico.get_storico_richieste_materiali")
    @patch("pages.storico.get_storico_richieste_assenze")
    def test_render_storico_complete(
        self,
        mock_ass,
        mock_mat,
        mock_rel,
        mock_int,
        mock_area,
        mock_md,
        mock_exp,
        mock_input,
        mock_sub,
        mock_tabs,
    ):
        # Mock tabs
        t1, t2, t3, t4 = MagicMock(), MagicMock(), MagicMock(), MagicMock()
        mock_tabs.return_value = [t1, t2, t3, t4]

        # Data for interventions (tab1)
        mock_int.return_value = pd.DataFrame(
            [
                {
                    "id_report": 1,
                    "pdl": "P101",
                    "descrizione_attivita": "DESC1",
                    "nome_tecnico": "T1",
                    "stato_attivita": "Validato",
                    "data_riferimento_attivita": "2023-01-01",
                    "data_compilazione": "2023-01-02",
                    "testo_report": "TEST1",
                },
                {
                    "id_report": 2,
                    "pdl": "P101",
                    "descrizione_attivita": "DESC1_ALT",
                    "nome_tecnico": "T2",
                    "stato_attivita": "Validato",
                    "data_riferimento_attivita": "2023-01-05",
                    "data_compilazione": "2023-01-06",
                    "testo_report": "TEST2",
                },
            ]
        )

        # Data for relazioni (tab2)
        mock_rel.return_value = pd.DataFrame(
            [
                {
                    "id_relazione": "R1",
                    "data_intervento": "2023-02-01",
                    "tecnico_compilatore": "T1",
                    "partner": "T2",
                    "ora_inizio": "08:00",
                    "ora_fine": "12:00",
                    "corpo_relazione": "TEXT1",
                }
            ]
        )

        # Data for materiali (tab3)
        mock_mat.return_value = pd.DataFrame(
            [
                {
                    "id_storico": "M1",
                    "timestamp_richiesta": "2023-03-01 10:00",
                    "nome_richiedente": "T1",
                    "dettagli_richiesta": "MAT1",
                }
            ]
        )

        # Data for assenze (tab4)
        mock_ass.return_value = pd.DataFrame(
            [
                {
                    "id_storico": "A1",
                    "data_inizio": "2023-04-01",
                    "data_fine": "2023-04-05",
                    "tipo_assenza": "Ferie",
                    "nome_richiedente": "T1",
                    "note": "NOTE1",
                }
            ]
        )

        # Simulate search term (triggers line 37)
        mock_input.return_value = "P101"

        # Context managers
        mock_exp.return_value.__enter__.return_value = MagicMock()
        t1.__enter__.return_value = MagicMock()
        t2.__enter__.return_value = MagicMock()
        t3.__enter__.return_value = MagicMock()
        t4.__enter__.return_value = MagicMock()

        render_storico_tab()

        # Verifiche
        mock_sub.assert_any_call("Archivio Report di Intervento Validati")
        mock_exp.assert_called()  # Should have expanders for PDL and single interventions
        mock_md.assert_called()
        mock_area.assert_called()

    @patch("streamlit.tabs")
    @patch("streamlit.success")
    @patch("pages.storico.get_validated_intervention_reports")
    @patch("pages.storico.get_validated_reports")
    @patch("pages.storico.get_storico_richieste_materiali")
    @patch("pages.storico.get_storico_richieste_assenze")
    def test_render_storico_empty(
        self, mock_ass, mock_mat, mock_rel, mock_int, mock_succ, mock_tabs
    ):
        mock_tabs.return_value = [MagicMock() for _ in range(4)]
        mock_int.return_value = pd.DataFrame()
        mock_rel.return_value = pd.DataFrame()
        mock_mat.return_value = pd.DataFrame()
        mock_ass.return_value = pd.DataFrame()

        render_storico_tab()

        mock_succ.assert_any_call("Non ci sono report di intervento validati nell'archivio.")
        mock_succ.assert_any_call("Nessuna richiesta di materiali nello storico.")


if __name__ == "__main__":
    unittest.main()
