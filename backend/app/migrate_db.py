import logging
from sqlalchemy import text
from app.database import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate():
    """Manual migration to add confluence_details to trade_setups table."""
    try:
        with engine.connect() as conn:
            logger.info("Checking if confluence_details column exists...")
            # Check if column exists
            result = conn.execute(text("SHOW COLUMNS FROM trade_setups LIKE 'confluence_details'"))
            if not result.fetchone():
                logger.info("Adding confluence_details column to trade_setups table...")
                conn.execute(text("ALTER TABLE trade_setups ADD COLUMN confluence_details JSON DEFAULT NULL AFTER confluence_score"))
                conn.commit()
                logger.info("Column added successfully.")
            else:
                logger.info("Column already exists.")
    except Exception as e:
        logger.error(f"Migration failed: {e}")

if __name__ == "__main__":
    migrate()
