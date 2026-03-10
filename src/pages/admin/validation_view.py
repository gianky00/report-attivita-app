"""
Interfaccia per la validazione finale dei report attività e delle relazioni di reperibilità.
Gestisce il flusso di approvazione e il trasferimento dei dati nello storico definitivo.
"""

import pandas as pd
import streamlit as st

from constants import ICONS, STATI_ATTIVITA
from modules.db_manager import (
    delete_reports_by_ids,
    get_reports_to_validate,
    get_unvalidated_relazioni,
    process_and_commit_validated_relazioni,
    process_and_commit_validated_reports,
)


def render_report_validation_tab(user_matricola: str) -> None:
    """Gestisce la tabella di validazione dei report tecnici inviati."""
    st.subheader("Validazione Report Tecnici")
    st.info(
        """
    Questa sezione permette di validare i report inviati dai tecnici.
    - I report in attesa vengono caricati automaticamente.
    - Puoi modificare il **Testo Report** e lo **Stato Attività** direttamente nella tabella.
    - Seleziona uno o più report e clicca "Cancella" per rimuoverli definitivamente in caso di errore.
    - Clicca "Valida e Salva Modifiche" per processare i report, scriverli su Excel e rimuoverli da questa coda.
    """,
        icon=ICONS["INFO"],
    )

    reports_df = get_reports_to_validate()

    if reports_df.empty:
        st.success("Nessun nuovo report da validare al momento.", icon=ICONS["CHECK"])
        return

    reports_df.insert(0, "valida", True)
    reports_df.insert(1, "delete", False)
    st.markdown("---")
    st.markdown(f"**Ci sono {len(reports_df)} report in attesa di validazione.**")

    # Funzione per colorare le righe in base allo stato
    def color_rows(row: pd.Series) -> list[str]:
        stato = row["stato_attivita"]
        color = ""
        if stato == "TERMINATA":
            color = "background-color: rgba(40, 167, 69, 0.2)"  # Verde trasparente
        elif stato == "IN CORSO":
            color = "background-color: rgba(255, 193, 7, 0.2)"  # Giallo trasparente
        elif stato == "SOSPESA":
            color = "background-color: rgba(111, 66, 193, 0.2)"  # Viola trasparente
        elif stato == "NON SVOLTA":
            color = "background-color: rgba(220, 53, 69, 0.2)"  # Rosso trasparente

        return [color] * len(row)

    disabled_cols = [
        "id_report",
        "pdl",
        "descrizione_attivita",
        "matricola_tecnico",
        "nome_tecnico",
        "data_compilazione",
        "data_riferimento_attivita",
    ]

    # Applichiamo lo stile prima del data_editor
    styled_df = reports_df.style.apply(color_rows, axis=1)

    edited_df = st.data_editor(
        styled_df,
        key="validation_editor",
        num_rows="dynamic",
        width="stretch",
        column_config={
            "valida": st.column_config.CheckboxColumn(
                "Valida", help="Seleziona per validare il report.", default=True
            ),
            "delete": st.column_config.CheckboxColumn(
                "Cancella", help="Seleziona per cancellare il report.", default=False
            ),
            "id_report": None,
            "pdl": st.column_config.Column("PdL", width="small"),
            "descrizione_attivita": st.column_config.Column("Descrizione", width="medium"),
            "matricola_tecnico": None,
            "nome_tecnico": st.column_config.Column("Tecnico", width="small"),
            "stato_attivita": st.column_config.SelectboxColumn(
                "Stato",
                width="small",
                options=STATI_ATTIVITA,
                required=True,
            ),
            "testo_report": st.column_config.TextColumn("Report", width="large"),
            "data_compilazione": st.column_config.DatetimeColumn(
                "Data Compilazione", format="DD/MM/YYYY HH:mm", width="small"
            ),
            "data_riferimento_attivita": None,
            "nome": None,
            "cognome": None,
            "tecnico_nome": None,
            "tecnico_cognome": None,
            "team": st.column_config.Column("Team", width="medium"),
            "ore_lavoro": None,
        },
        disabled=disabled_cols,
    )

    st.markdown("---")
    col1, col2, _ = st.columns([2.5, 2.5, 4])

    with col1:
        # Validiamo solo quelli selezionati per la validazione e NON selezionati per la cancellazione
        reports_to_validate_df = edited_df[edited_df["valida"] & ~edited_df["delete"]]
        if not reports_to_validate_df.empty and st.button(
            f"Valida {len(reports_to_validate_df)} Report Selezionati",
            type="primary",
            use_container_width=True,
            icon=ICONS["CHECK"],
        ):
            reports_to_process = reports_to_validate_df.drop(columns=["delete", "valida"])
            with st.spinner("Salvataggio dei report validati in corso..."):
                if process_and_commit_validated_reports(reports_to_process.to_dict("records")):  # type: ignore[arg-type]
                    st.success("Report validati e salvati con successo!", icon=ICONS["CHECK"])
                    st.rerun()
                else:
                    st.error(
                        "Si è verificato un errore durante il salvataggio dei report.",
                        icon=ICONS["ERROR"],
                    )

    with col2:
        reports_to_delete_df = edited_df[edited_df["delete"]]
        if not reports_to_delete_df.empty and st.button(
            f"Cancella {len(reports_to_delete_df)} Report",
            use_container_width=True,
            icon=ICONS["DELETE"],
        ):
            ids_to_delete = reports_to_delete_df["id_report"].tolist()
            if delete_reports_by_ids(ids_to_delete):
                st.success(
                    f"{len(ids_to_delete)} report sono stati cancellati con successo.",
                    icon=ICONS["CHECK"],
                )
                st.rerun()
            else:
                st.error("Errore durante la cancellazione dei report.", icon=ICONS["ERROR"])


def render_relazioni_validation_tab(matricola_utente: str) -> None:
    """Gestisce la validazione delle relazioni di reperibilità."""
    st.subheader("Validazione Relazioni Inviate")
    unvalidated_relazioni_df = get_unvalidated_relazioni()
    if unvalidated_relazioni_df.empty:
        st.success("Nessuna nuova relazione da validare al momento.", icon=ICONS["CHECK"])
    else:
        st.info(
            f"Ci sono {len(unvalidated_relazioni_df)} relazioni da validare.", icon=ICONS["INFO"]
        )
        if "data_intervento" in unvalidated_relazioni_df.columns:
            unvalidated_relazioni_df["data_intervento"] = pd.to_datetime(
                unvalidated_relazioni_df["data_intervento"], errors="coerce"
            ).dt.strftime("%d/%m/%Y")
        if "timestamp_invio" in unvalidated_relazioni_df.columns:
            unvalidated_relazioni_df["timestamp_invio"] = pd.to_datetime(
                unvalidated_relazioni_df["timestamp_invio"], errors="coerce"
            ).dt.strftime("%d/%m/%Y %H:%M")
        edited_relazioni_df = st.data_editor(
            unvalidated_relazioni_df,
            num_rows="dynamic",
            key="relazioni_editor",
            width="stretch",
            column_config={
                "corpo_relazione": st.column_config.TextColumn(width="large"),
                "id_relazione": st.column_config.Column(disabled=True),
                "timestamp_invio": st.column_config.Column(disabled=True),
            },
        )
        if st.button("Salva Relazioni Validate", type="primary", icon=ICONS["CHECK"]):
            with st.spinner("Salvataggio delle relazioni in corso..."):
                if process_and_commit_validated_relazioni(edited_relazioni_df, matricola_utente):
                    st.success("Relazioni validate e salvate con successo!", icon=ICONS["CHECK"])
                    st.rerun()
                else:
                    st.error(
                        "Si è verificato un errore durante il salvataggio delle relazioni.",
                        icon=ICONS["ERROR"],
                    )
