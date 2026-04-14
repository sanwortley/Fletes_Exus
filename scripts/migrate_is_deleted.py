"""
Migration: Agregar columnas faltantes a PostgreSQL
Ejecutar LOCAL: python scripts/migrate_is_deleted.py
Ejecutar EN RENDER: rendr python scripts/migrate_is_deleted.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(override=True)

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL no encontrada en .env")
    exit(1)

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
elif DATABASE_URL.startswith("mysql://"):
    DATABASE_URL = DATABASE_URL.replace("mysql://", "mysql+pymysql://", 1)

from sqlalchemy import create_engine, text

engine = create_engine(DATABASE_URL)

migrations = [
    ("quotes", "is_deleted", "BOOLEAN DEFAULT FALSE"),
    ("quotes", "voided_at", "TIMESTAMP"),
    ("quotes", "notas_confirmacion", "TEXT"),
    ("quotes", "fecha_hora_preferida", "TEXT"),
    ("users", "failed_logins", "INTEGER DEFAULT 0"),
    ("users", "lock_until", "TIMESTAMP"),
]

def main():
    print(f"=== MIGRATION ===")
    db_name = DATABASE_URL.split('@')[-1].split('/')[-1] if '@' in DATABASE_URL else "unknown"
    print(f"Database: {db_name}")
    
    with engine.connect() as conn:
        for table, col, definition in migrations:
            try:
                sql = f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {definition}"
                conn.execute(text(sql))
                print(f"  [OK] {table}.{col}")
            except Exception as e:
                err_str = str(e)
                if "already exists" in err_str.lower() or "duplicate" in err_str.lower():
                    print(f"  [SKIP] {table}.{col} (ya existe)")
                else:
                    print(f"  [ERR] {table}.{col} - {err_str[:60]}")
        
        conn.commit()
    
    print("=== DONE ===")

if __name__ == "__main__":
    main()