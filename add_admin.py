import sqlite3
import bcrypt

DB_NAME = "schedario.db"

def add_admin_user():
    conn = None
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        # Hash a password for the admin user
        password = "admin_password"
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

        # Insert the admin user
        cursor.execute("""
            INSERT INTO contatti (Matricola, "Nome Cognome", Ruolo, PasswordHash)
            VALUES (?, ?, ?, ?)
        """, ("admin", "Admin User", "Amministratore", hashed_password.decode('utf-8')))

        conn.commit()
        print("Admin user added successfully.")

    except sqlite3.Error as e:
        print(f"Error adding admin user: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    add_admin_user()
