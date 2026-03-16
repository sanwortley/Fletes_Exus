
import sys
import os

# Agregar el directorio raíz al path para importar el backend
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import Session, engine
from backend.models.models import dbUser
from backend.security.security_auth import hash_password
from sqlmodel import select

def seed_admin():
    with Session(engine) as session:
        # Verificar si ya existe
        statement = select(dbUser).where(dbUser.username == "admin")
        existing_user = session.exec(statement).first()
        
        if existing_user:
            print("El usuario 'admin' ya existe en MySQL.")
            return

        print("Creando usuario administrador en MySQL...")
        new_user = dbUser(
            username="admin",
            email="admin@exus.com.ar",
            password_hash=hash_password("Fletes111125##"),
            role="admin"
        )
        session.add(new_user)
        session.commit()
        print("¡Usuario 'admin' creado exitosamente con la contraseña: Fletes111125##")

if __name__ == "__main__":
    seed_admin()
