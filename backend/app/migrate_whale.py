import logging
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.database import engine, Base
from app.models.whale import Chain, WhaleThreshold, Wallet, WhaleTransaction # Import to register models

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate():
    """Create whale tracker tables and seed initial data."""
    try:
        logger.info("Creating whale tracker tables if they don't exist...")
        Base.metadata.create_all(bind=engine)
        logger.info("Tables created successfully.")
        
        # Seed default chains and thresholds
        with Session(engine) as session:
            chains = ["ethereum", "bsc", "solana"]
            for chain_id in chains:
                # Add chain if not exists
                chain = session.query(Chain).filter_by(id=chain_id).first()
                if not chain:
                    logger.info(f"Adding chain {chain_id}")
                    session.add(Chain(id=chain_id, name=chain_id.capitalize()))
                    
                # Add threshold if not exists
                threshold = session.query(WhaleThreshold).filter_by(chain_id=chain_id).first()
                if not threshold:
                    logger.info(f"Adding default threshold for {chain_id}")
                    session.add(WhaleThreshold(chain_id=chain_id, usd_threshold=500000.0))
            
            session.commit()
            logger.info("Seed data inserted successfully.")
            
    except Exception as e:
        logger.error(f"Migration failed: {e}")

if __name__ == "__main__":
    migrate()
