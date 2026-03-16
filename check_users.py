from sqlmodel import Session, select, create_engine
import sys
import os

sys.path.append(os.path.join(os.getcwd(), "backend"))
from models.models import dbUser

DATABASE_URL = "sqlite:///./database.db"
engine = create_engine(DATABASE_URL)

def check_db():
    with Session(engine) as session:
        statement = select(dbUser)
        users = session.exec(statement).all()
        print(f"Total users: {len(users)}")
        for u in users:
            print(f"User: {u.username}, Email: {u.email}, Fails: {u.failed_logins}, Lock: {u.lock_until}")

if __name__ == "__main__":
    check_db()
