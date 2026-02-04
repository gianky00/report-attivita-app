import logging
import sys
from datetime import datetime
from pathlib import Path

# Configure logging to ensure output is captured
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)


def check_pyarmor_license():
    """
    Checks for the existence of a pyarmor.rkey file and, if present,
    reads it to find and log the license expiration date.
    """
    license_file = Path("pyarmor.rkey")
    if license_file.exists():
        try:
            for line in license_file.read_text(encoding="utf-8").splitlines():
                if "Expired Date:" in line:
                    # Assuming the format is "Expired Date: YYY-MM-DD"
                    expired_date_str = line.split("Expired Date:")[1].strip()
                    expired_date = datetime.strptime(
                        expired_date_str, "%Y-%m-%d"
                    ).date()
                    logging.info(f"PyArmor license expiration date: {expired_date}")
                    return
            logging.info(
                "PyArmor license file found, but no expiration date was specified within the file."
            )
        except Exception as e:
            logging.error(f"Error reading PyArmor license file: {e}")
    else:
        logging.info("PyArmor license file not found. Skipping license check.")
