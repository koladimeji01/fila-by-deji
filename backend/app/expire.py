"""Sweep expired reservations. Schedule hourly in production (not yet deployed)."""
from .database import SessionLocal
from .reservations import expire_holds

if __name__ == '__main__':
    with SessionLocal() as db:
        count = expire_holds(db)
    print(f'Expired {count} reservations')
