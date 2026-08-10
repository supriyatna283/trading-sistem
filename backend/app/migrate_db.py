import logging
from sqlalchemy import text
from app.database import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate():
    """Manual migration to add columns to tables."""
    try:
        with engine.connect() as conn:
            # 1. trade_setups: confluence_details
            logger.info("Checking if confluence_details column exists...")
            result = conn.execute(text("SHOW COLUMNS FROM trade_setups LIKE 'confluence_details'"))
            if not result.fetchone():
                logger.info("Adding confluence_details column to trade_setups table...")
                conn.execute(text("ALTER TABLE trade_setups ADD COLUMN confluence_details JSON DEFAULT NULL AFTER confluence_score"))
                conn.commit()
                logger.info("confluence_details added successfully.")
            else:
                logger.info("confluence_details already exists.")

            # 2. wallets: win_rate and pnl_usd
            logger.info("Checking if win_rate and pnl_usd columns exist in wallets...")
            
            result_wr = conn.execute(text("SHOW COLUMNS FROM wallets LIKE 'win_rate'"))
            if not result_wr.fetchone():
                logger.info("Adding win_rate column to wallets table...")
                conn.execute(text("ALTER TABLE wallets ADD COLUMN win_rate FLOAT DEFAULT 0.0"))
                conn.commit()
                logger.info("win_rate added successfully.")
                
            result_pnl = conn.execute(text("SHOW COLUMNS FROM wallets LIKE 'pnl_usd'"))
            if not result_pnl.fetchone():
                logger.info("Adding pnl_usd column to wallets table...")
                conn.execute(text("ALTER TABLE wallets ADD COLUMN pnl_usd FLOAT DEFAULT 0.0"))
                conn.commit()
                logger.info("pnl_usd added successfully.")
                
    except Exception as e:
        logger.error(f"Migration failed: {e}")

if __name__ == "__main__":
    migrate()
