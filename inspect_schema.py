import sqlite3

DB_NAME = "schedario.db"

def get_schema():
    """Prints the schema of the access_logs table."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(access_logs)")
    schema = cursor.fetchall()
    for column in schema:
        print(column)
    conn.close()

if __name__ == "__main__":
    get_schema()
