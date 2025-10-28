import sqlite3

DB_NAME = "schedario.db"

def list_users():
    conn = None
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        cursor.execute("SELECT Matricola, \"Nome Cognome\" FROM contatti")
        users = cursor.fetchall()

        if users:
            print("Users in the database:")
            for user in users:
                print(f"- Matricola: {user[0]}, Nome Cognome: {user[1]}")
        else:
            print("No users found in the database.")

    except sqlite3.Error as e:
        print(f"Error listing users: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    list_users()
