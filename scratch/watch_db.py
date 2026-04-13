import time
import os
from sqlmodel import Session, select, func
from backend.database import engine
from backend.models.models import dbQuote

def watch_db():
    print("Watcher started. Monitoring 'quotes' table...")
    last_ids = set()
    while True:
        try:
            with Session(engine) as session:
                current_quotes = session.exec(select(dbQuote)).all()
                current_ids = {q.id for q in current_quotes}
                
                if last_ids and current_ids != last_ids:
                    deleted = last_ids - current_ids
                    added = current_ids - last_ids
                    if deleted:
                        print(f"!!! DELETION DETECTED: IDs {deleted}")
                        for qid in deleted:
                            # Try to find what happened? No, it's gone.
                            pass
                    if added:
                        print(f"New records: IDs {added}")
                
                last_ids = current_ids
        except Exception as e:
            print(f"Watcher error: {e}")
        time.sleep(0.5)

if __name__ == "__main__":
    watch_db()
