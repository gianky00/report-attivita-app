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
from modules.db_manager import get_globally_excluded_activities


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
def _carica_giornaliera_mese(path: Path) -> dict | None:
    """Carica tutte le schede di un file Excel giornaliero con caching."""
    try:
        return pd.read_excel(path, sheet_name=None, header=None)
    except Exception:
        return None


def _load_day_sheet(giorno: int, mese: int, anno: int) -> pd.DataFrame | None:
    """Individua e carica la scheda corrispondente a un giorno specifico."""
    path = Path(config.PATH_GIORNALIERA_BASE) / f"Giornaliera {mese:02d}-{anno}.xlsm"
    sheets = _carica_giornaliera_mese(path)
    if not sheets:
        return None
    target = next((n for n in sheets.keys() if str(giorno) in n.split()), None)
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
) -> dict[tuple, dict]:
    """Raggruppa le attività e i membri del team coinvolti."""
    collezionate: dict[tuple, dict] = {}
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
            collezionate[key]["team"][member]["orari"].add(f"{r[10]}-{r[11]}")
    return collezionate


def _get_member_role(member_name: str, df_contatti: pd.DataFrame) -> str:
    """Recupera il ruolo di un membro del team dal dataframe contatti."""
    for _, cr in df_contatti.iterrows():
        if _match_partial_name(member_name, cr["Nome Cognome"]):
            return str(cr.get("Ruolo", "Tecnico"))
    return "Tecnico"


def trova_attivita(
    matricola: str, giorno: int, mese: int, anno: int, df_contatti: pd.DataFrame
) -> list[dict[str, Any]]:
    """Estrae le attività dal file Excel per un dato giorno e tecnico."""
    try:
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
            final.append(v)

        excluded = get_globally_excluded_activities()
        return [t for t in final if f"{t['pdl']}-{t['attivita']}" not in excluded]
    except Exception:
        return []


def get_all_assigned_activities(
    matricola: str, df_contatti: pd.DataFrame, days: int = 60
) -> list[dict[str, Any]]:
    """Recupera tutte le attività assegnate negli ultimi N giorni."""
    all_act = []
    today = datetime.date.today()
    for i in range(days):
        d = today - datetime.timedelta(days=i)
        activities = trova_attivita(matricola, d.day, d.month, d.year, df_contatti)
        for a in activities:
            a["Data Assegnamento"] = d
            all_act.append(a)
    return all_act