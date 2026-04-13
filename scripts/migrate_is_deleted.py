import sqlite3
import os

DB_PATH = "database.db"

def migrate():
    if not os.path.exists(DB_PATH):
        print(f"Database {DB_PATH} not found. Skipping migration.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        print("Checking for 'is_deleted' column in 'quotes' table...")
        cursor.execute("PRAGMA table_info(quotes)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if "is_deleted" not in columns:
            print("Adding 'is_deleted' column...")
            cursor.execute("ALTER TABLE quotes ADD COLUMN is_deleted BOOLEAN DEFAULT 0")
            print("Column added successfully.")
        else:
            print("Column 'is_deleted' already exists.")
            
        conn.commit()
    except Exception as e:
        print(f"Migration error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
