"""
Funzioni di utilità generale per la manipolazione di dati e orari.
"""

from datetime import datetime, timedelta
import pytz


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
        
    duration = (end_dt - start_dt).total_seconds() / 3600
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
    return [
        f"{start.strftime('%H:%M')} - {end.strftime('%H:%M')}" for start, end in merged
    ]
