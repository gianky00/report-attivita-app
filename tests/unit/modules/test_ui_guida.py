"""
Test unitari per la pagina guida.
Copre src/pages/guida.py.
"""

import streamlit as st

from pages.guida import render_guida_tab


def test_render_guida_tab_tecnico(mocker):
    mocker.patch("streamlit.write")
    mocker.patch("streamlit.info")
    mocker.patch("streamlit.expander", return_value=mocker.MagicMock())
    mocker.patch("streamlit.markdown")

    render_guida_tab("Tecnico")
    assert st.write.called
    assert st.info.called


def test_render_guida_tab_admin(mocker):
    mocker.patch("streamlit.write")
    mocker.patch("streamlit.info")
    mocker.patch("streamlit.expander", return_value=mocker.MagicMock())
    mocker.patch("streamlit.markdown")

    render_guida_tab("Amministratore")
    assert st.write.called
    assert st.info.called
