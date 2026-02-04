import sqlite3
import sys

DB_NAME = "schedario.db"

def reset_user_2fa(matricola):
    """
    Resets the 2FA secret for a given user Matricola in the database.
    """
    conn = None
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        # Set the 2FA_Secret to NULL for the specified user
        cursor.execute("UPDATE contatti SET \"2FA_Secret\" = NULL WHERE Matricola = ?", (matricola,))

        if cursor.rowcount > 0:
            conn.commit()
            print(f"2FA for user with Matricola '{matricola}' has been reset successfully.")
            print("The user will be prompted to set up 2FA on their next login.")
        else:
            print(f"User with Matricola '{matricola}' not found in the database. No changes were made.")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python reset_admin_2fa.py <Matricola>")
        sys.exit(1)

    user_matricola = sys.argv[1]
    reset_user_2fa(user_matricola)
