import sys
import unittest
from pathlib import Path
from unittest.mock import patch


# Mock streamlit cache_data before importing the module
def mock_cache(func):
    def clear():
        pass
    func.clear = clear
    return func

# Aggiungi 'src' al path
root_dir = Path(__file__).parent.parent.parent.parent
sys.path.append(str(root_dir / "src"))

# Patch manuale di st.cache_data prima dell'import
import streamlit as st

st.cache_data = mock_cache

from modules.knowledge_base import carica_knowledge_core


class TestKnowledgeBase(unittest.TestCase):

    @patch("modules.knowledge_base.st")
    @patch("modules.knowledge_base.config")
    @patch("modules.knowledge_base.Path.exists")
    @patch("modules.knowledge_base.Path.read_text")
    def test_carica_knowledge_core_success(self, mock_read_text, mock_exists, mock_config, mock_st):
        # Setup mock
        mock_exists.return_value = True
        mock_read_text.return_value = '{"key": "value"}'
        mock_config.PATH_KNOWLEDGE_CORE = "dummy.json"

        # Saltiamo il decoratore cache_data se è presente
        func = carica_knowledge_core
        if hasattr(func, "__wrapped__"):
            func = func.__wrapped__

        # Execute
        result = func()

        # Verify
        self.assertEqual(result, {"key": "value"})
        mock_st.error.assert_not_called()

    @patch("modules.knowledge_base.st")
    @patch("modules.knowledge_base.config")
    @patch("modules.knowledge_base.Path.exists")
    def test_carica_knowledge_core_not_found(self, mock_exists, mock_config, mock_st):
        # Setup mock
        mock_exists.return_value = False
        mock_config.PATH_KNOWLEDGE_CORE = "missing.json"

        # Saltiamo il decoratore cache_data se è presente
        func = carica_knowledge_core
        if hasattr(func, "__wrapped__"):
            func = func.__wrapped__

        # Execute
        result = func()

        # Verify
        self.assertIsNone(result)
        mock_st.error.assert_called_once()
        self.assertIn("non trovato", mock_st.error.call_args[0][0])

    @patch("modules.knowledge_base.st")
    @patch("modules.knowledge_base.config")
    @patch("modules.knowledge_base.Path.exists")
    @patch("modules.knowledge_base.Path.read_text")
    def test_carica_knowledge_core_invalid_json(self, mock_read_text, mock_exists, mock_config, mock_st):
        # Setup mock
        mock_exists.return_value = True
        mock_read_text.return_value = '{invalid: json}'
        mock_config.PATH_KNOWLEDGE_CORE = "invalid.json"

        # Saltiamo il decoratore cache_data se è presente
        func = carica_knowledge_core
        if hasattr(func, "__wrapped__"):
            func = func.__wrapped__

        # Execute
        result = func()

        # Verify
        self.assertIsNone(result)
        mock_st.error.assert_called_once()
        self.assertIn("non è un JSON valido", mock_st.error.call_args[0][0])

if __name__ == "__main__":
    unittest.main()
