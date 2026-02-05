"""
Test di concorrenza per l'invio asincrono di email.
"""

import threading
import time
import pytest
from modules.email_sender import invia_email_con_outlook_async

def test_email_rapid_fire_threading(mocker):
    """Verifica che l'invio di molteplici email in parallelo non causi crash."""
    # Mock del subprocesso per non eseguire realmente Outlook
    mock_sub = mocker.patch("modules.email_sender._send_email_subprocess")
    
    # Lanciamo 10 email quasi simultaneamente
    threads = []
    for i in range(10):
        invia_email_con_outlook_async(f"Subject {i}", f"Body {i}")
    
    # Attendiamo un tempo sufficiente per l'avvio dei thread
    time.sleep(0.5)
    
    # Verifichiamo che siano state fatte 10 chiamate al subprocesso
    assert mock_sub.call_count == 10
