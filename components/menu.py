import streamlit as st

def render_sidebar(role):
    """Renders the sidebar navigation for the application."""

    # Initialize session state for selected page if not present
    if 'selected_page' not in st.session_state:
        st.session_state.selected_page = "Attività di Oggi"

    if st.session_state.sidebar_state == 'expanded':
        st.sidebar.title("Menu")

        with st.sidebar:
            # Attività Assegnate (with sub-menu)
            with st.expander("Attività Assegnate", expanded=True):
                if st.button("Attività di Oggi"):
                    st.session_state.selected_page = "Attività di Oggi"
                    st.rerun()
                if st.button("Recupero Attività"):
                    st.session_state.selected_page = "Recupero Attività"
                    st.rerun()
                if st.button("Attività Validate"):
                    st.session_state.selected_page = "Attività Validate"
                    st.rerun()
                if role in ["Tecnico", "Amministratore"]:
                    if st.button("Compila Relazione"):
                        st.session_state.selected_page = "Compila Relazione"
                        st.rerun()

            # Other main menu items
            if st.button("📅 Gestione Turni"):
                st.session_state.selected_page = "Gestione Turni"
                st.rerun()
            if st.button("Richieste"):
                st.session_state.selected_page = "Richieste"
                st.rerun()
            if st.button("Storico"):
                st.session_state.selected_page = "Storico"
                st.rerun()
            if st.button("❓ Guida"):
                st.session_state.selected_page = "Guida"
                st.rerun()

            # Admin section
            if role == "Amministratore":
                st.sidebar.title("Admin")
                with st.expander("Dashboard Admin", expanded=False):
                     if st.button("Dashboard Caposquadra"):
                        st.session_state.selected_page = "Dashboard Caposquadra"
                        st.rerun()
                     if st.button("Dashboard Tecnica"):
                        st.session_state.selected_page = "Dashboard Tecnica"
                        st.rerun()

    return st.session_state.selected_page
