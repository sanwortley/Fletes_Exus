import os
import sys
from sqlmodel import Session, select, create_engine
from backend.database import engine
from backend.models.models import dbQuote

def check_recent_quotes():
    with Session(engine) as session:
        # Check last 20 quotes
        statement = select(dbQuote).order_by(dbQuote.created_at.desc()).limit(20)
        results = session.exec(statement).all()
        print(f"--- Ultimos 20 pedidos ---")
        for q in results:
            print(f"ID:{q.id} | Nom:{q.nombre_cliente} | Est:{q.estado} | Turno:{q.fecha_turno} | Created:{q.created_at}")

        # Check for any quote that might have been marked as 'anulado' or 'realizado' recently
        statement_h = select(dbQuote).where(dbQuote.estado.in_(["anulado", "realizado", "rechazado"])).order_by(dbQuote.created_at.desc()).limit(10)
        results_h = session.exec(statement_h).all()
        print(f"\n--- Ultimos Historicos/Rechazados ---")
        for q in results_h:
            print(f"ID:{q.id} | Nom:{q.nombre_cliente} | Est:{q.estado} | Turno:{q.fecha_turno}")

if __name__ == "__main__":
    check_recent_quotes()
