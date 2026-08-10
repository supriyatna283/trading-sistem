import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.database import engine

def migrate():
    print("Starting database migration...")
    with engine.begin() as conn:
        try:
            conn.execute(text("ALTER TABLE wallets ADD COLUMN win_rate FLOAT DEFAULT 0.0;"))
            print("Added win_rate column.")
        except Exception as e:
            print(f"win_rate column might already exist: {e}")
            
        try:
            conn.execute(text("ALTER TABLE wallets ADD COLUMN pnl_usd FLOAT DEFAULT 0.0;"))
            print("Added pnl_usd column.")
        except Exception as e:
            print(f"pnl_usd column might already exist: {e}")
            
    print("Migration complete!")

if __name__ == "__main__":
    migrate()
