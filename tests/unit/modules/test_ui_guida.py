"""
Test unitari per la pagina guida.
Copre src/pages/guida.py.
"""

import pytest
import streamlit as st
from pages.guida import render_guida_tab

def test_render_guida_tab_tecnico(mocker):
    mocker.patch("streamlit.title")
    mocker.patch("streamlit.write")
    mocker.patch("streamlit.info")
    mocker.patch("streamlit.expander", return_value=mocker.MagicMock())
    mocker.patch("streamlit.markdown")
    
    render_guida_tab("Tecnico")
    assert st.title.called

def test_render_guida_tab_admin(mocker):
    mocker.patch("streamlit.title")
    mocker.patch("streamlit.write")
    mocker.patch("streamlit.info")
    mocker.patch("streamlit.expander", return_value=mocker.MagicMock())
    mocker.patch("streamlit.markdown")
    
    render_guida_tab("Amministratore")
    assert st.title.called
