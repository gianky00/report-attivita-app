"""
Interfaccia amministrativa per la gestione dell'IA e del Knowledge Core.
Permette la revisione dei suggerimenti dei tecnici e l'aggiornamento degli indici.
"""

import datetime

import streamlit as st

import learning_module as learning_module


def render_ia_management_tab():
    """Interfaccia principale per la gestione dell'IA."""
    st.subheader("Gestione Intelligenza Artificiale")
    ia_tabs = st.tabs(["Revisione Conoscenze", "Memoria IA"])

    with ia_tabs[0]:
        _render_knowledge_review()
    with ia_tabs[1]:
        _render_ia_memory_update()


def _render_knowledge_review():
    """Logica di revisione del Knowledge Core."""
    st.markdown("### 🧠 Revisione Voci del Knowledge Core")
    unreviewed = learning_module.load_unreviewed_knowledge()
    pending = [e for e in unreviewed if e.get("stato") == "in attesa di revisione"]

    if not pending:
        st.success("🎉 Nessuna nuova voce da revisionare!")
        return

    st.info(f"Ci sono {len(pending)} nuove voci da revisionare.")
    for i, entry in enumerate(pending):
        _render_review_expander(entry, i == 0)


def _render_ia_memory_update():
    """Interfaccia per l'aggiornamento dell'indice vettoriale dell'IA."""
    st.subheader("Gestione Modello IA")
    st.info("Aggiorna la base di conoscenza dell'IA con le nuove relazioni inviate.")
    if st.button("🧠 Aggiorna Memoria IA", type="primary"):
        with st.spinner("Ricostruzione dell'indice in corso..."):
            result = learning_module.build_knowledge_base()
        if result.get("success"):
            st.success(result.get("message"))
            st.cache_data.clear()
        else:
            st.error(result.get("message"))


def _render_review_expander(entry, is_expanded):
    """Expander per la singola voce del Knowledge Core in revisione."""
    label = f"**Voce ID:** `{entry['id']}` - **Attività:** {entry['attivita_collegata']}"
    with st.expander(label, expanded=is_expanded):
        sugg_dt = datetime.datetime.fromisoformat(entry["data_suggerimento"]).strftime("%d/%m/%Y %H:%M")
        st.markdown(f"*Suggerito da: **{entry['suggerito_da']}** il {sugg_dt}*")
        st.markdown(f"*PdL di riferimento: `{entry['pdl']}`*")
        st.write("**Dettagli:**")
        st.json(entry["dettagli_report"])
        st.markdown("---")
        st.markdown("**Azione di Integrazione**")

        c1, c2 = st.columns(2)
        key = c1.text_input("Chiave Attrezzatura", key=f"k_{entry['id']}")
        name = c2.text_input("Nome Visualizzato", key=f"n_{entry['id']}")

        if st.button("✅ Integra", key=f"int_{entry['id']}", type="primary"):
            if key and name:
                _integrate_entry(entry, key, name)
            else:
                st.warning("Fornire sia chiave che nome.")


def _integrate_entry(entry, equipment_key, display_name):
    """Esegue l'integrazione effettiva di una voce nel Knowledge Core."""
    first_question = {
        "id": "sintomo_iniziale",
        "text": "Qual era il sintomo principale?",
        "options": {k.lower().replace(" ", "_"): v for k, v in entry["dettagli_report"].items()},
    }
    details = {"equipment_key": equipment_key, "display_name": display_name, "new_question": first_question}

    result = learning_module.integrate_knowledge(entry["id"], details)
    if result.get("success"):
        st.success("Integrata!")
        st.cache_data.clear()
        st.rerun()
    else:
        st.error(f"Errore: {result.get('error')}")
