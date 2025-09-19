import json
from streamlit_browser_storage import LocalStorage

# Use a consistent key for the local storage instance to avoid collisions
storage = LocalStorage(key="report_attivita_offline_storage")

# The key under which the list of offline reports will be saved in the browser
OFFLINE_REPORTS_KEY = "offline_reports"

def get_offline_reports() -> list:
    """
    Loads the list of offline reports from the browser's localStorage.
    Returns a list of report dictionaries, or an empty list if none are found.
    """
    value = storage.get(OFFLINE_REPORTS_KEY)
    if value:
        try:
            # Values from storage are JSON strings, so they need to be decoded
            return json.loads(value)
        except json.JSONDecodeError:
            # Handle cases where the stored data is corrupted
            return []
    return []

def save_report_offline(report_data: dict):
    """
    Adds a new report to the list of offline reports in localStorage.
    If a report for the same PdL already exists, it will be replaced.

    :param report_data: A dictionary containing the report details.
    """
    reports = get_offline_reports()
    pdl_to_replace = report_data.get('pdl')

    # Remove any existing report for the same PdL to avoid duplicates
    if pdl_to_replace:
        reports = [r for r in reports if r.get('pdl') != pdl_to_replace]

    reports.append(report_data)
    storage.set(OFFLINE_REPORTS_KEY, json.dumps(reports))

def remove_report_from_offline(pdl: str):
    """
    Removes a specific report from the offline list, identified by its PdL.

    :param pdl: The PdL string of the report to remove.
    """
    reports = get_offline_reports()
    reports_to_keep = [r for r in reports if r.get('pdl') != pdl]
    storage.set(OFFLINE_REPORTS_KEY, json.dumps(reports_to_keep))

def clear_all_offline_reports():
    """
    Clears all offline reports from localStorage. This is useful after a successful sync.
    """
    storage.delete(OFFLINE_REPORTS_KEY)
