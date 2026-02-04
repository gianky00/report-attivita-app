import pandas as pd
import streamlit as st

from modules.db_manager import (
    get_storico_richieste_assenze,
    get_storico_richieste_materiali,
    get_validated_intervention_reports,
    get_validated_reports,
)


def render_storico_tab():
    """
    Renderizza la sezione "Storico" con le sottoschede per le attività
    e le relazioni validate.
    """
    st.subheader("Archivio Storico")

    st.markdown('<div class="card">', unsafe_allow_html=True)
    tab1, tab2, tab3, tab4 = st.tabs(
        [
            "**Storico Attività**",
            "**Storico Relazioni**",
            "**Storico Materiali**",
            "**Storico Assenze**",
        ]
    )

    with tab1:
        st.subheader("Archivio Report di Intervento Validati")
        df_attivita = get_validated_intervention_reports()

        if not df_attivita.empty:
            # Search functionality
            search_term = st.text_input(
                "Cerca per PdL, descrizione o tecnico...", key="search_attivita"
            )
            if search_term:
                df_attivita = df_attivita[
                    df_attivita["pdl"].str.contains(search_term, case=False, na=False)
                    | df_attivita["descrizione_attivita"].str.contains(
                        search_term, case=False, na=False
                    )
                    | df_attivita["nome_tecnico"].str.contains(
                        search_term, case=False, na=False
                    )
                ]

            # Group by PDL
            grouped_by_pdl = df_attivita.groupby("pdl")

            for pdl, group in grouped_by_pdl:
                # Get the description from the first row of the group
                descrizione_pdl = group["descrizione_attivita"].iloc[0]
                expander_title = f"**PDL {pdl}** - {descrizione_pdl}"

                with st.expander(expander_title):
                    # Sort interventions by date
                    group["data_riferimento_attivita"] = pd.to_datetime(
                        group["data_riferimento_attivita"]
                    )
                    sorted_group = group.sort_values(
                        by="data_riferimento_attivita", ascending=False
                    )

                    for _, row in sorted_group.iterrows():
                        rif_dt = row["data_riferimento_attivita"]
                        data_intervento_str = rif_dt.strftime("%d/%m/%Y")
                        # Titolo dell'expander interno con la sola data
                        sub_expander_title = f"Intervento del {data_intervento_str}"

                        with st.expander(sub_expander_title):
                            # Dettagli all'interno dell'expander
                            st.markdown(
                                f"**Report compilato da:** {row['nome_tecnico']}"
                            )
                            st.markdown(f"**Stato:** {row['stato_attivita']}")
                            comp_dt = pd.to_datetime(row["data_compilazione"])
                            st.markdown(
                                f"**Data Compilazione:** "
                                f"{comp_dt.strftime('%d/%m/%Y %H:%M')}"
                            )
                            st.text_area(
                                "Report:",
                                value=row["testo_report"],
                                height=200,
                                disabled=True,
                                key=f"report_{row['id_report']}",
                            )
        else:
            st.success("Non ci sono report di intervento validati nell'archivio.")

    with tab2:
        st.subheader("Archivio Relazioni di Reperibilità Validate")
        df_relazioni = get_validated_reports("relazioni")
        if not df_relazioni.empty:
            # Ordina le relazioni per data di intervento
            if "data_intervento" in df_relazioni.columns:
                df_relazioni["data_intervento"] = pd.to_datetime(
                    df_relazioni["data_intervento"]
                )
                df_relazioni = df_relazioni.sort_values(
                    by="data_intervento", ascending=False
                )

            for _, row in df_relazioni.iterrows():
                # Formatta la data per una visualizzazione più pulita
                data_intervento_str = (
                    row["data_intervento"].strftime("%d/%m/%Y")
                    if pd.notna(row["data_intervento"])
                    else "Data non disponibile"
                )

                t_comp = row.get("tecnico_compilatore", "N/D")
                t_part = row.get("partner", "N/D")
                expander_title = (
                    f"**{data_intervento_str}** - Tecnico: **{t_comp}** - "
                    f"Partner: **{t_part}**"
                )

                with st.expander(expander_title):
                    o_in = row.get("ora_inizio", "N/D")
                    o_out = row.get("ora_fine", "N/D")
                    st.markdown(f"**Orario:** dalle {o_in} alle {o_out}")
                    st.markdown("**Relazione:**")
                    # Usa una formattazione che rispetti gli a capo
                    st.text_area(
                        "",
                        value=row.get("corpo_relazione", "Nessun testo."),
                        height=200,
                        disabled=True,
                        key=f"rel_{row['id_relazione']}",
                    )
        else:
            st.success("Non ci sono relazioni validate nell'archivio.")

    with tab3:
        st.subheader("Archivio Richieste Materiali Approvate")
        df_materiali = get_storico_richieste_materiali()
        if not df_materiali.empty:
            for _, row in df_materiali.iterrows():
                t_rich = pd.to_datetime(row["timestamp_richiesta"])
                timestamp_str = t_rich.strftime("%d/%m/%Y %H:%M")
                n_rich = row.get("nome_richiedente", "N/D")
                expander_title = f"**{timestamp_str}** - Richiedente: **{n_rich}**"
                with st.expander(expander_title):
                    st.text_area(
                        "Dettagli Richiesta",
                        value=row.get("dettagli_richiesta", "Nessun dettaglio."),
                        height=150,
                        disabled=True,
                        key=f"mat_{row['id_storico']}",
                    )
        else:
            st.success("Nessuna richiesta di materiali nello storico.")

    with tab4:
        st.subheader("Archivio Richieste Assenze Approvate")
        df_assenze = get_storico_richieste_assenze()
        if not df_assenze.empty:
            for _, row in df_assenze.iterrows():
                data_inizio_str = pd.to_datetime(row["data_inizio"]).strftime(
                    "%d/%m/%Y"
                )
                data_fine_str = pd.to_datetime(row["data_fine"]).strftime("%d/%m/%Y")
                tipo_ass = row.get("tipo_assenza", "N/D")
                n_rich = row.get("nome_richiedente", "N/D")
                expander_title = (
                    f"**{tipo_ass}** dal **{data_inizio_str}** al "
                    f"**{data_fine_str}** - Richiedente: **{n_rich}**"
                )
                with st.expander(expander_title):
                    st.text_area(
                        "Note",
                        value=row.get("note", "Nessuna nota."),
                        height=100,
                        disabled=True,
                        key=f"ass_{row['id_storico']}",
                    )
        else:
            st.success("Nessuna richiesta di assenze nello storico.")
    st.markdown("</div>", unsafe_allow_html=True)
