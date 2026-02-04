"""
Gestione centralizzata delle eccezioni per l'applicazione Streamlit.
Fornisce decoratori per catturare errori, loggarli in formato JSON e mostrare UI di fallback.
"""

import functools
from collections.abc import Callable
from typing import Any

import streamlit as st
from src.core.logging import get_logger, with_context

logger = get_logger(__name__)


def safe_streamlit_run(func: Callable) -> Callable:
    """
    Decoratore per rendere sicura l'esecuzione di una pagina o di un componente Streamlit.
    Cattura ogni eccezione, genera un trace_id, logga l'errore e mostra un messaggio elegante.
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        with with_context() as trace_id:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # Logga l'errore con contesto completo e trace_id
                logger.critical(
                    f"Crash dell'applicazione rilevato in {func.__name__}: {e}",
                    extra={"extra_data": {"trace_id": trace_id}},
                    exc_info=True,
                )

                # Interfaccia di errore per l'utente
                st.error("### 🚨 Si è verificato un errore imprevisto")
                st.markdown(f"""
                L'operazione è stata interrotta per garantire la sicurezza dei dati.

                **Cosa puoi fare:**
                1. Riprova a caricare la pagina.
                2. Se il problema persiste, contatta il supporto tecnico fornendo il codice di errore qui sotto.

                **Codice Errore (Trace ID):** `{trace_id}`
                """)

                if st.checkbox("Mostra dettagli tecnici (solo per amministratori)"):
                    st.exception(e)

                st.stop()

    return wrapper
