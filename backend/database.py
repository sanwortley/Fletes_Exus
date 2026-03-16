import os
from sqlmodel import create_engine, SQLModel, Session
from dotenv import load_dotenv

load_dotenv(override=True)

# Preferimos usar una variable de entorno DATABASE_URL
# Para desarrollo local si no hay Postgres/MySQL, usamos SQLite
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./database.db")

# Caso especial para Render/Postgres que usa 'postgres://' en vez de 'postgresql://'
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Caso especial para MySQL para asegurar el driver pymysql si no está especificado
if DATABASE_URL.startswith("mysql://"):
    DATABASE_URL = DATABASE_URL.replace("mysql://", "mysql+pymysql://", 1)

# El motor de la base de datos
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args, echo=False)

def init_db():
    from .models import models  # Importamos los modelos para registrarlos en SQLModel
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine, expire_on_commit=False) as session:
        yield session
