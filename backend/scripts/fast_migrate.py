import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from app.database import SessionLocal
from app.models.whale import Wallet, WhaleTransaction, WhaleDirection
from sqlalchemy import update, select

def main():
    db = SessionLocal()
    try:
        print("Starting fast DB migration...")
        
        # 1. First get all exchange wallet IDs
        exchange_wallet_ids = db.query(Wallet.id).filter(Wallet.entity_type == 'exchange').all()
        exchange_ids = [row[0] for row in exchange_wallet_ids]
        
        print(f"Found {len(exchange_ids)} exchange wallets.")
        if not exchange_ids:
            print("No exchange wallets found! Please run the first part of the migration again.")
            return

        # 2. Bulk update INFLOW (to exchange, from not exchange)
        # Using SQLAlchemy bulk update
        print("Updating INFLOWs...")
        res_inflow = db.execute(
            update(WhaleTransaction)
            .where(WhaleTransaction.to_wallet_id.in_(exchange_ids))
            .where(WhaleTransaction.from_wallet_id.not_in(exchange_ids))
            .values(direction=WhaleDirection.INFLOW)
        )
        print(f"Updated {res_inflow.rowcount} inflows.")

        # 3. Bulk update OUTFLOW (from exchange, to not exchange)
        print("Updating OUTFLOWs...")
        res_outflow = db.execute(
            update(WhaleTransaction)
            .where(WhaleTransaction.from_wallet_id.in_(exchange_ids))
            .where(WhaleTransaction.to_wallet_id.not_in(exchange_ids))
            .values(direction=WhaleDirection.OUTFLOW)
        )
        print(f"Updated {res_outflow.rowcount} outflows.")

        # 4. Bulk update TRANSFER (all others)
        print("Updating TRANSFERs...")
        res_transfer_1 = db.execute(
            update(WhaleTransaction)
            .where(WhaleTransaction.from_wallet_id.in_(exchange_ids))
            .where(WhaleTransaction.to_wallet_id.in_(exchange_ids))
            .values(direction=WhaleDirection.TRANSFER)
        )
        res_transfer_2 = db.execute(
            update(WhaleTransaction)
            .where(WhaleTransaction.from_wallet_id.not_in(exchange_ids))
            .where(WhaleTransaction.to_wallet_id.not_in(exchange_ids))
            .values(direction=WhaleDirection.TRANSFER)
        )
        print(f"Updated {res_transfer_1.rowcount + res_transfer_2.rowcount} transfers.")

        db.commit()
        print("Bulk update finished.")

    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    main()
