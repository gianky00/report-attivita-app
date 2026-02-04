import os
import sys
import win32com.client as win32
import pythoncom

def run_macro():
    """
    Opens the 'Database_Report_Attivita.xlsm' workbook and runs the 'AggiornaRisposte' macro.
    """
    excel = None
    workbook = None
    try:
        # Build the absolute path to the Excel file relative to the script's location
        script_dir = os.path.dirname(os.path.abspath(__file__))
        excel_file_path = os.path.join(script_dir, "Database_Report_Attivita.xlsm")

        if not os.path.exists(excel_file_path):
            print(f"ERRORE: File non trovato: {excel_file_path}", file=sys.stderr)
            sys.exit(1)

        # Initialize COM for this thread
        pythoncom.CoInitialize()
        excel = win32.Dispatch('Excel.Application')
        excel.Visible = False  # Run in the background

        workbook = excel.Workbooks.Open(excel_file_path)

        # Run the macro. The macro name is sufficient if it's in a standard module.
        excel.Application.Run("AggiornaRisposte")

        workbook.Save()
        workbook.Close(SaveChanges=True)
        print("SUCCESSO: Macro eseguita e file salvato correttamente.")

    except Exception as e:
        print(f"ERRORE: Si è verificato un'eccezione: {e}", file=sys.stderr)
        if excel:
            excel.Quit() # Attempt to close Excel on error
        sys.exit(1)

    finally:
        # Ensure Excel is closed and COM objects are released
        if excel:
            excel.Quit()
        del workbook
        del excel
        pythoncom.CoUninitialize()

if __name__ == "__main__":
    run_macro()
