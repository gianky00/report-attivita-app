import datetime

import pandas as pd
import streamlit as st

from constants import ICONS
from modules.db_manager import (
    get_pdl_programmazione,
    get_storico_richieste_materiali,
    get_validated_intervention_reports,
    get_validated_reports,
)
from pages.archivio_view import render_archivio_page


def render_storico_tab() -> None:
    """
    Renderizza la sezione "Storico" con le sottoschede per le attività,
    le relazioni validate e le schede tecniche.
    """
    st.header(f"{ICONS['STORICO']} Storico")

    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        [
            f"{ICONS['STORICO']} Attività",
            f"{ICONS['PROGRAMMAZIONE']} Programmazione",
            f"{ICONS['RELATION']} Relazioni",
            f"{ICONS['ARCHIVIO']} Schede",
            f"{ICONS['MATERIAL']} Materiali",
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
                    | df_attivita["nome_tecnico"].str.contains(search_term, case=False, na=False)
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
                            st.markdown(f"**Report compilato da:** {row['nome_tecnico']}")
                            st.markdown(f"**Stato:** {row['stato_attivita']}")
                            comp_dt = pd.to_datetime(row["data_compilazione"])
                            st.markdown(
                                f"**Data Compilazione:** {comp_dt.strftime('%d/%m/%Y %H:%M')}"
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
        st.subheader("Archivio Programmazione PDL")
        c1, c2, c3 = st.columns([1, 1, 1])
        today = datetime.date.today()

        with c1:
            data_inizio = st.date_input(
                "Dalla data", today - datetime.timedelta(days=30), format="DD/MM/YYYY"
            )
        with c2:
            data_fine = st.date_input("Alla data", today, format="DD/MM/YYYY")

        df_prog = get_pdl_programmazione(data_inizio.isoformat(), data_fine.isoformat())

        if df_prog.empty:
            st.warning("Nessun PDL trovato per il periodo selezionato.")
        else:
            with c3:
                search_prog = st.text_input(
                    "Cerca (Team, PDL o Descrizione)", "", key="search_storico_prog"
                )

            if search_prog:
                df_prog = df_prog[
                    df_prog["pdl"].str.contains(search_prog, case=False, na=False)
                    | df_prog["team"].str.contains(search_prog, case=False, na=False)
                    | df_prog["descrizione"].str.contains(search_prog, case=False, na=False)
                ]

            display_df = df_prog.copy()
            display_df.columns = [
                "PDL",
                "Data Intervento",
                "Tecnico",
                "Descrizione",
                "Team",
                "Stato",
                "Tipo",
                "Pianificato il",
                "Report Inviato",
                "Validato il",
            ]

            for col in ["Pianificato il", "Report Inviato", "Validato il"]:
                display_df[col] = pd.to_datetime(display_df[col], errors="coerce").dt.strftime(
                    "%d/%m/%Y - %H:%M"
                )
                display_df[col] = display_df[col].fillna("-")

            def color_rows(row: pd.Series) -> list[str]:
                val = row["Stato"]
                color = "black"
                bg_color = "transparent"
                if val == "PIANIFICATO":
                    color = "#6c757d"
                elif val == "INVIATO":
                    color = "#856404"  # Darker yellow for text
                    bg_color = "rgba(255, 193, 7, 0.2)"
                elif val == "VALIDATO":
                    color = "#155724"  # Darker green for text
                    bg_color = "rgba(40, 167, 69, 0.2)"
                elif val == "NON SVOLTA":
                    color = "#721c24"  # Darker red for text
                    bg_color = "rgba(220, 53, 69, 0.2)"
                elif val == "SOSPESA":
                    color = "#383d41"
                    bg_color = "rgba(111, 66, 193, 0.2)"

                style = f"color: {color}; background-color: {bg_color}; font-weight: bold"
                return [style] * len(row)

            st.dataframe(
                display_df.style.apply(color_rows, axis=1),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "PDL": st.column_config.TextColumn("PDL", width="small"),
                    "Data Intervento": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
                    "Stato": st.column_config.TextColumn("Stato", width="small"),
                },
            )

    with tab3:
        st.subheader("Archivio Relazioni di Reperibilità Validate")
        df_relazioni = get_validated_reports("relazioni")
        if not df_relazioni.empty:
            # Ordina le relazioni per data di intervento
            if "data_intervento" in df_relazioni.columns:
                df_relazioni["data_intervento"] = pd.to_datetime(df_relazioni["data_intervento"])
                df_relazioni = df_relazioni.sort_values(by="data_intervento", ascending=False)

            for _, row in df_relazioni.iterrows():
                # Formatta la data per una visualizzazione più pulita
                data_intervento_str = (
                    row["data_intervento"].strftime("%d/%m/%Y")
                    if pd.notna(row["data_intervento"])
                    else "Data non disponibile"
                )

                t_comp = row.get("tecnico_compilatore", "N/D")
                pdl_rel = row.get("pdl", "N/D")
                expander_title = (
                    f"**{data_intervento_str}** - PdL: **{pdl_rel}** - Tecnico: **{t_comp}**"
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

    with tab4:
        render_archivio_page()

    with tab5:
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
