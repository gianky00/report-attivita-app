"""
Logica complessa per il parsing dei file Excel 'Giornaliera'.
"""

import datetime
import re
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

import config
from modules.db_manager import get_excluded_activities_for_user


def _match_partial_name(partial_name: str, full_name: str) -> bool:
    """Confronta un nome parziale con un nome completo gestendo iniziali multiple."""
    if not partial_name or not full_name:
        return False
    # Normalizza separando le iniziali puntate (es. G.B. -> G B)
    norm_partial = partial_name.replace(".", " ").lower()
    parts = [p for p in norm_partial.split() if p]
    full = full_name.lower().split()
    initials = {p for p in parts if len(p) == 1}
    names = {p for p in parts if len(p) > 1}
    if not names.issubset(set(full)):
        return False
    rem_initials = {p[0] for p in (set(full) - names)}
    return initials.issubset(rem_initials)


@st.cache_data(ttl=3600)
def _carica_giornaliera_mese(path: Path) -> dict[str, pd.DataFrame] | None:
    """Carica tutte le schede di un file Excel giornaliero con caching."""
    try:
        result: dict[str, pd.DataFrame] | None = pd.read_excel(path, sheet_name=None, header=None)
        return result
    except Exception:
        return None


def _load_day_sheet(giorno: int, mese: int, anno: int) -> pd.DataFrame | None:
    """Individua e carica la scheda corrispondente a un giorno specifico."""
    # Otteniamo il percorso dinamico dall'anno tramite la nuova funzione root in config
    base_path_str = config.get_giornaliera_path(anno)
    base_path = Path(base_path_str)

    from core.logging import get_logger

    logger = get_logger(__name__)

    if not base_path.exists():
        logger.error(f"Directory base non accessibile: {base_path}")
        return None

    path = base_path / f"Giornaliera {mese:02d}-{anno}.xlsm"

    if not path.exists():
        logger.warning(f"File Excel non trovato: {path}")
        return None

    logger.info(f"Caricamento file giornaliera: {path}")
    sheets = _carica_giornaliera_mese(path)
    if not sheets:
        return None
    target = next((n for n in sheets if str(giorno) in n.split()), None)
    return sheets[target].iloc[3:45] if target else None


def _get_user_pdls(df_range: pd.DataFrame, full_name: str) -> set[str]:
    """Identifica i codici PdL in cui il tecnico è coinvolto."""
    pdls = set()
    for _, r in df_range.iterrows():
        if len(r) > 9 and _match_partial_name(str(r[5]), full_name):
            pdls.update(re.findall(r"(\d{6}/[CS]|\d{6})", str(r[9])))
    return pdls


def _collect_team_info(
    df_range: pd.DataFrame, pdls: set[str], df_contatti: pd.DataFrame
) -> dict[tuple[str, str], dict[str, Any]]:
    """Raggruppa le attività e i membri del team coinvolti."""
    collezionate: dict[tuple[str, str], dict[str, Any]] = {}
    for _, r in df_range.iterrows():
        if len(r) < 12 or pd.isna(r[9]):
            continue
        found_pdls = re.findall(r"(\d{6}/[CS]|\d{6})", str(r[9]))
        if not any(p in pdls for p in found_pdls):
            continue

        descs = [line.strip() for line in str(r[6]).splitlines() if line.strip()]
        for p, d in zip(found_pdls, descs, strict=False):
            if p not in pdls:
                continue
            key = (p, d)
            if key not in collezionate:
                collezionate[key] = {"pdl": p, "attivita": d, "team": {}}

            member = str(r[5]).strip()
            if member not in collezionate[key]["team"]:
                role = _get_member_role(member, df_contatti)
                collezionate[key]["team"][member] = {"ruolo": role, "orari": set()}

            # Recupero ore direttamente dalla colonna M (indice 12)
            try:
                # Se il valore è numerico lo prendiamo, altrimenti proviamo a convertirlo
                ore_membro = float(r[12]) if pd.notna(r[12]) else 0.0
            except (ValueError, TypeError):
                ore_membro = 0.0

            collezionate[key]["team"][member]["orari"].add(f"{r[10]}-{r[11]}")
            # Sommiamo le ore totali per l'attività (totale ore-uomo da colonna M)
            collezionate[key]["ore_totali"] = collezionate[key].get("ore_totali", 0.0) + ore_membro
    return collezionate


def _get_member_role(member_name: str, df_contatti: pd.DataFrame) -> str:
    """Recupera il ruolo di un membro del team dal dataframe contatti."""
    for _, cr in df_contatti.iterrows():
        if _match_partial_name(member_name, cr["Nome Cognome"]):
            return str(cr.get("Ruolo", "Tecnico"))
    return "Tecnico"


def estrai_tutte_le_attivita_giorno(giorno: int, mese: int, anno: int) -> list[dict[str, Any]]:
    """Estrae tutte le attività dal file Excel per un dato giorno, senza filtri."""
    df_range = _load_day_sheet(giorno, mese, anno)
    if df_range is None:
        return []

    pdls_totali: set[str] = set()
    for _, r in df_range.iterrows():
        if len(r) > 9 and pd.notna(r[9]):
            pdls_totali.update(re.findall(r"(\d{6}/[CS]|\d{6})", str(r[9])))

    if not pdls_totali:
        return []

    # Per raccogliere il team, passiamo un df_contatti vuoto o finto se non serve il ruolo esatto qui
    # Oppure recuperiamo i nomi reali se disponibili
    collezionate: dict[tuple[str, str], dict[str, Any]] = {}
    for _, r in df_range.iterrows():
        if len(r) < 12 or pd.isna(r[9]):
            continue
        found_pdls = re.findall(r"(\d{6}/[CS]|\d{6})", str(r[9]))

        descs = [line.strip() for line in str(r[6]).splitlines() if line.strip()]
        for p, d in zip(found_pdls, descs, strict=False):
            key = (p, d)
            if key not in collezionate:
                collezionate[key] = {
                    "pdl": p,
                    "attivita": d,
                    "tecnico_assegnato": str(r[5]).strip(),
                    "team": set(),
                    "ore": 0.0,
                }

            collezionate[key]["team"].add(str(r[5]).strip())
            import contextlib

            with contextlib.suppress(ValueError, TypeError):
                collezionate[key]["ore"] += float(r[12]) if pd.notna(r[12]) else 0.0

    final = []
    for v in collezionate.values():
        v["team"] = ", ".join(sorted(v["team"]))
        final.append(v)

    return final


def trova_attivita(
    matricola: str, giorno: int, mese: int, anno: int, df_contatti: pd.DataFrame
) -> list[dict[str, Any]]:
    """Estrae le attività dal file Excel per un dato giorno e tecnico."""
    try:
        # SIMULAZIONE PER TEST: Se la matricola è 472, restituisco un'attività finta
        if matricola == "472":
            return [
                {
                    "pdl": "123456/S",
                    "attivita": "MANUTENZIONE STRAORDINARIA VALVOLE - TEST SIMULATO",
                    "team": [
                        {"nome": "Domenico Spinali", "ruolo": "Tecnico", "orari": ["08:00-16:00"]},
                        {
                            "nome": "Giancarlo Allegretti",
                            "ruolo": "Aiutante",
                            "orari": ["08:00-16:00"],
                        },
                    ],
                }
            ]

        user = df_contatti[df_contatti["Matricola"] == matricola]
        if user.empty:
            return []
        full_name = user.iloc[0]["Nome Cognome"]

        df_range = _load_day_sheet(giorno, mese, anno)
        if df_range is None:
            return []

        pdls = _get_user_pdls(df_range, full_name)
        if not pdls:
            return []

        collezionate = _collect_team_info(df_range, pdls, df_contatti)
        final = []
        for v in collezionate.values():
            v["team"] = [
                {"nome": k, "ruolo": t["ruolo"], "orari": sorted(t["orari"])}
                for k, t in v["team"].items()
            ]
            v["ore_lavoro"] = v.get("ore_totali", 0.0)
            final.append(v)

        excluded = get_excluded_activities_for_user(matricola)
        return [t for t in final if f"{t['pdl']}-{t['attivita']}" not in excluded]
    except Exception as e:
        from core.logging import get_logger

        get_logger(__name__).error(f"Errore in trova_attivita ({giorno}/{mese}/{anno}): {e}")
        return []


def get_all_assigned_activities(
    matricola: str, df_contatti: pd.DataFrame, days: int = 60
) -> list[dict[str, Any]]:
    """Recupera tutte le attività assegnate negli ultimi N giorni."""
    # Controllo rapido accessibilità base prima del ciclo
    base_path = Path(config.get_giornaliera_path())
    if not base_path.exists():
        from core.logging import get_logger

        get_logger(__name__).error(
            f"Impossibile recuperare attività: directory {base_path} non accessibile."
        )
        return []

    all_act = []
    today = datetime.date.today()
    for i in range(days):
        d = today - datetime.timedelta(days=i)
        activities = trova_attivita(matricola, d.day, d.month, d.year, df_contatti)
        for a in activities:
            a["Data Assegnamento"] = d
            all_act.append(a)
    return all_act
