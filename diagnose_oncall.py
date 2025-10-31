
import datetime
from modules.oncall_logic import get_on_call_pair

def print_oncall_schedule(start_date, months_to_show):
    """
    Prints the on-call schedule for a specified number of months.
    """
    print("--- On-Call Schedule Diagnosis ---")
    print(f"Start Date: {start_date.strftime('%d/%m/%Y')}")
    print("Rotation Rule: 7-day blocks, starting on a Friday.\n")

    current_date = start_date
    end_date = start_date + datetime.timedelta(days=months_to_show * 31)

    # Adjust to the first Friday to start the loop
    while current_date.weekday() != 4:
        current_date += datetime.timedelta(days=1)

    while current_date < end_date:
        start_of_period = current_date
        end_of_period = start_of_period + datetime.timedelta(days=6)

        pair = get_on_call_pair(start_of_period)
        (technician1, _), (technician2, _) = pair

        print(f"Period: {start_of_period.strftime('%d/%m/%Y')} - {end_of_period.strftime('%d/%m/%Y')}")
        print(f"  -> Assigned: {technician1}, {technician2}\n")

        # Move to the next Friday
        current_date += datetime.timedelta(days=7)

if __name__ == "__main__":
    # Start from a known date to ensure the output is predictable
    # Let's start from a few weeks before the problematic period
    start_from = datetime.date(2025, 10, 1)
    print_oncall_schedule(start_from, 6)
