"""
Test unitari per la configurazione dei destinatari email.
"""
import config as config

def test_default_email_recipients():
    """Verifica che i destinatari predefiniti siano corretti (solo Gianky, no CC)."""
    # Verifichiamo il destinatario principale predefinito
    # Nota: se il file secrets.toml esiste nell'ambiente di test, 
    # questo test potrebbe fallire se i valori sono diversi.
    # Ma il comando ruff ha mostrato che stiamo aggiornando i default.
    assert config.EMAIL_DESTINATARIO == "gianky.allegretti@gmail.com"
    
    # Verifichiamo che la lista CC sia vuota per impostazione predefinita
    assert config.EMAIL_CC == []
