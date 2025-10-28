import sqlite3

DB_NAME = "schedario.db"
ADMIN_MATRICOLA = "admin"

def reset_admin_2fa():
    """
    Resets the 2FA secret for the admin user in the database.
    """
    conn = None
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        # Set the 2FA_Secret to NULL for the admin user
        cursor.execute("UPDATE contatti SET \"2FA_Secret\" = NULL WHERE Matricola = ?", (ADMIN_MATRICOLA,))

        if cursor.rowcount > 0:
            conn.commit()
            print(f"2FA for user '{ADMIN_MATRICOLA}' has been reset successfully.")
            print("The user will be prompted to set up 2FA on their next login.")
        else:
            print(f"User '{ADMIN_MATRICOLA}' not found in the database. No changes were made.")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    reset_admin_2fa()
