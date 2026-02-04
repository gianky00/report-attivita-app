"""
Gestori dei form e dell'interfaccia utente (Facade).
Riesporta i componenti dai moduli specializzati.
"""

import streamlit as st

from src.components.forms.debriefing_form import render_debriefing_ui
from src.components.forms.shift_edit_form import render_edit_shift_form
from src.components.forms.relazione_oncall_form import (
    render_relazione_reperibilita_ui,
)

@st.cache_data
def to_csv(df):
    """Converte un dataframe in CSV per il download."""
    return df.to_csv(index=False).encode("utf-8")

__all__ = [
    "render_debriefing_ui",
    "render_edit_shift_form",
    "render_relazione_reperibilita_ui",
    "to_csv",
]
