"""
Componenti dell'interfaccia utente (Facade).
Riesporta i widget dai moduli specializzati.
"""

from components.ui.activity_ui import (
    visualizza_storico_organizzato,
    disegna_sezione_attivita,
)
from components.ui.navigation_ui import render_sidebar
from components.ui.notifications_ui import render_notification_center

__all__ = [
    "visualizza_storico_organizzato",
    "disegna_sezione_attivita",
    "render_sidebar",
    "render_notification_center",
]
