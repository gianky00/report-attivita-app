"""
Funzioni di utilità generale per la manipolazione di dati e orari.
"""

import base64
from datetime import datetime, timedelta
from pathlib import Path

import pytz


def render_svg_icon(icon_name: str, size: int = 24, color: str | None = None) -> str:
    """
    Legge un file SVG dalla cartella assets/icons e lo restituisce come stringa HTML.
    """
    icon_path = Path("assets/icons") / f"{icon_name}.svg"
    if not icon_path.exists():
        return ""

    # Inserisce dimensioni dinamiche
    svg_content = (
        icon_path.read_text(encoding="utf-8")
        .replace('width="24"', f'width="{size}"')
        .replace('height="24"', f'height="{size}"')
    )

    # Gestione colore: se fornito, sostituisce 'currentColor' o aggiunge lo stile
    if color:
        if 'stroke="currentColor"' in svg_content:
            svg_content = svg_content.replace('stroke="currentColor"', f'stroke="{color}"')
        elif 'fill="currentColor"' in svg_content:
            svg_content = svg_content.replace('fill="currentColor"', f'fill="{color}"')
        else:
            # Fallback: avvolge in uno span colorato se l'SVG non usa currentColor
            return f'<span style="vertical-align: middle; margin-right: 8px; display: inline-block; color: {color};">{svg_content}</span>'

    return f'<span style="vertical-align: middle; margin-right: 8px; display: inline-block;">{svg_content}</span>'


def colored_label(
    text: str,
    icon_material: str | None = None,
    color: str | None = None,
    font_size: str = "inherit",
    bold: bool = False,
) -> str:
    """Genera una stringa HTML per un'etichetta con icona Material colorata."""
    style = f"color: {color};" if color else ""
    style += f" font-size: {font_size};"
    if bold:
        style += " font-weight: bold;"

    icon_html = ""
    if icon_material:
        # Estrae il nome dell'icona da :material/nome:
        icon_name = icon_material.replace(":material/", "").replace(":", "")
        icon_html = f'<span class="material-icons-sharp" style="vertical-align: middle; margin-right: 4px;">{icon_name}</span>'

    return f'<span style="{style}">{icon_html}{text}</span>'


def get_svg_as_base64(icon_name: str) -> str:
    """Restituisce l'SVG codificato in base64 per l'uso in CSS."""
    icon_path = Path("assets/icons") / f"{icon_name}.svg"
    if not icon_path.exists():
        return ""
    svg_content = icon_path.read_text(encoding="utf-8")
    b64 = base64.b64encode(svg_content.encode("utf-8")).decode("utf-8")
    return f"data:image/svg+xml;base64,{b64}"


def calculate_shift_duration(start_iso: str, end_iso: str, tz_name: str = "Europe/Rome") -> float:
    """
    Calcola la durata effettiva di un turno in ore, gestendo il passaggio DST.
    """
    tz = pytz.timezone(tz_name)
    start_dt = tz.localize(datetime.fromisoformat(start_iso))
    end_dt = tz.localize(datetime.fromisoformat(end_iso))

    # Se la fine è precedente all'inizio (mezzanotte), aggiungi un giorno
    if end_dt < start_dt:
        end_dt += timedelta(days=1)

    duration: float = (end_dt - start_dt).total_seconds() / 3600
    return round(duration, 2)


def merge_time_slots(time_slots: list[str]) -> list[str]:
    """
    Unisce intervalli di tempo sovrapposti o contigui.
    Esempio: ["08:00-10:00", "10:00-12:00"] -> ["08:00 - 12:00"]

    Args:
        time_slots: Lista di stringhe nel formato "HH:MM-HH:MM".

    Returns:
        Lista di stringhe formattate con gli intervalli uniti.
    """
    if not time_slots:
        return []

    # Convert string times to datetime objects for sorting
    slots = []
    for slot in time_slots:
        try:
            start_time = datetime.strptime(slot.split("-")[0].strip(), "%H:%M")
            end_time = datetime.strptime(slot.split("-")[1].strip(), "%H:%M")
            slots.append((start_time, end_time))
        except (ValueError, IndexError):
            # Handle cases with invalid format or single time values gracefully
            continue

    if not slots:
        return []

    slots.sort()

    merged = []
    current_start, current_end = slots[0]

    for next_start, next_end in slots[1:]:
        if next_start <= current_end:
            # Overlapping or contiguous interval, merge
            current_end = max(current_end, next_end)
        else:
            # Disjoint interval, finalize the current one and start a new one
            merged.append((current_start, current_end))
            current_start, current_end = next_start, next_end

    merged.append((current_start, current_end))

    # Convert back to string format
    return [f"{start.strftime('%H:%M')} - {end.strftime('%H:%M')}" for start, end in merged]
