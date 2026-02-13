"""
Componenti dell'interfaccia utente (Facade).
Riesporta i widget dai moduli specializzati.
"""

from components.ui.activity_ui import (
    disegna_sezione_attivita,
    visualizza_storico_organizzato,
)
from components.ui.navigation_ui import render_sidebar
from components.ui.notifications_ui import render_notification_center

__all__ = [
    "disegna_sezione_attivita",
    "render_notification_center",
    "render_sidebar",
    "visualizza_storico_organizzato",
]
