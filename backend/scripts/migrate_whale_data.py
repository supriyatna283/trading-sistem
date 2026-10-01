import os
import sys
from pathlib import Path

# Add backend directory to sys.path so we can import app
sys.path.append(str(Path(__file__).parent.parent))

from app.database import SessionLocal
from app.models.whale import Wallet, WhaleTransaction, SmartWallet
from app.services.wallet_labeler import KNOWN_HOT_WALLETS

def main():
    db = SessionLocal()
    try:
        print("Starting data migration...")
        
        # 1. Update Exchange Wallets
        print("\n--- Updating Exchange Wallets ---")
        all_wallets = db.query(Wallet).all()
        exchange_count = 0
        for w in all_wallets:
            lower_addr = w.address.lower()
            if lower_addr in KNOWN_HOT_WALLETS:
                w.entity_type = "exchange"
                w.label = KNOWN_HOT_WALLETS[lower_addr]
                w.entity_source = "static_list"
                exchange_count += 1
                
        db.commit()
        print(f"Updated {exchange_count} wallets to 'exchange'.")
        
        # 2. Update Smart Money Wallets
        print("\n--- Updating Smart Money Wallets ---")
        smart_money_candidates = db.query(Wallet).filter(
            Wallet.entity_type != "exchange",
            Wallet.pnl_usd > 5000000,  # $5M+
            Wallet.win_rate > 70.0
        ).all()
        
        smart_count = 0
        for w in smart_money_candidates:
            w.entity_type = "smart_money"
            
            # Check if exists in SmartWallet
            existing = db.query(SmartWallet).filter(SmartWallet.wallet_id == w.id).first()
            if not existing:
                sw = SmartWallet(
                    wallet_id=w.id,
                    alias=f"Smart Whale {str(w.id)[:4]}",
                    win_rate=w.win_rate,
                    pnl_usd=w.pnl_usd,
                    added_by="migration",
                    is_active=True
                )
                db.add(sw)
                smart_count += 1
                
        db.commit()
        print(f"Updated {len(smart_money_candidates)} wallets to 'smart_money'. Added {smart_count} to SmartWallet table.")
        
        # 3. Update Transaction Directions
        print("\n--- Updating Transaction Directions ---")
        transactions = db.query(WhaleTransaction).all()
        
        # Create a fast lookup for wallet entity types
        wallet_types = {w.id: w.entity_type for w in all_wallets}
        
        inflow_count = 0
        outflow_count = 0
        transfer_count = 0
        
        for tx in transactions:
            from_type = wallet_types.get(tx.from_wallet_id)
            to_type = wallet_types.get(tx.to_wallet_id)
            
            if to_type == "exchange" and from_type != "exchange":
                tx.direction = "INFLOW"
                inflow_count += 1
            elif from_type == "exchange" and to_type != "exchange":
                tx.direction = "OUTFLOW"
                outflow_count += 1
            else:
                tx.direction = "TRANSFER"
                transfer_count += 1
                
        db.commit()
        print(f"Updated transaction directions:")
        print(f"  INFLOW:   {inflow_count}")
        print(f"  OUTFLOW:  {outflow_count}")
        print(f"  TRANSFER: {transfer_count}")
        
        print("\nMigration completed successfully!")
        
    except Exception as e:
        print(f"Error during migration: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    main()
