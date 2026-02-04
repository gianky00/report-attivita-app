"""
Componenti dell'interfaccia utente (Facade).
Riesporta i widget dai moduli specializzati.
"""

from src.components.ui.activity_ui import (
    visualizza_storico_organizzato,
    disegna_sezione_attivita,
)
from src.components.ui.navigation_ui import render_sidebar
from src.components.ui.notifications_ui import render_notification_center

__all__ = [
    "visualizza_storico_organizzato",
    "disegna_sezione_attivita",
    "render_sidebar",
    "render_notification_center",
]
