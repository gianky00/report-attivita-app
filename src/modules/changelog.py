from pathlib import Path

import streamlit as st


def get_latest_changes() -> str:
    """Legge le ultime modifiche dal file CHANGELOG.md."""
    changelog_path = Path("CHANGELOG.md")
    if not changelog_path.exists():
        return "Nessuna informazione disponibile."

    try:
        content = changelog_path.read_text(encoding="utf-8")
        # Restituiamo solo la sezione della versione corrente (la prima)
        sections = content.split("## ")
        if len(sections) > 1:
            return "## " + sections[1]
        return content
    except Exception:
        return "Errore nel caricamento del changelog."


def render_changelog_ui() -> None:
    """Renderizza il changelog in formato Streamlit."""
    changes = get_latest_changes()
    st.markdown(changes)
