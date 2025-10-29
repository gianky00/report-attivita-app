
import streamlit as st

def render_sidebar(role):
    """
    Renders the custom sidebar navigation inside a container.
    Handles page selection and auto-closing of the menu.
    """
    def menu_button(label):
        if st.button(label, key=f"menu_{label.lower().replace(' ', '_')}"):
            st.session_state.selected_page = label
            st.session_state.menu_visible = False  # Auto-close menu
            st.rerun()

    st.title("Menu")

    with st.expander("Attività Assegnate", expanded=True):
        menu_button("Attività di Oggi")
        menu_button("Recupero Attività")
        menu_button("Attività Validate")
        if role in ["Tecnico", "Amministratore"]:
            menu_button("Compila Relazione")

    menu_button("Gestione Turni")
    menu_button("Richieste")
    menu_button("Storico")
    menu_button("Guida")

    if role == "Amministratore":
        st.title("Admin")
        with st.expander("Dashboard Admin", expanded=False):
            menu_button("Dashboard Caposquadra")
            menu_button("Dashboard Tecnica")
