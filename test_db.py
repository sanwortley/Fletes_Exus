import os
from sqlmodel import create_engine, Session, select, text
from dotenv import load_dotenv

load_dotenv(override=True)
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./database.db")

# Caso especial para Render/Postgres que usa 'postgres://' en vez de 'postgresql://'
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

print(f"Probando conexión a base de datos: {DATABASE_URL}")

try:
    engine = create_engine(DATABASE_URL)
    with Session(engine) as session:
        # Una consulta simple para verificar conexión
        session.execute(text("SELECT 1"))
        print("✅ Conexión exitosa a la base de datos SQL!")
except Exception as e:
    print(f"❌ Error de conexión: {e}")
    exit(1)
