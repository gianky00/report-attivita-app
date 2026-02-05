"""
Test unitari per la configurazione dei destinatari email.
"""
import config as config

def test_default_email_recipients():
    """Verifica che i destinatari predefiniti siano corretti (solo Gianky, no CC)."""
    # Verifichiamo il destinatario principale predefinito
    assert "gianky.allegretti@gmail.com" in config.EMAIL_DESTINATARIO
    assert "giancarlo.allegretti@coemi.it" in config.EMAIL_DESTINATARIO
    
    # Verifichiamo che la lista CC sia vuota per impostazione predefinita
    assert config.EMAIL_CC == []
