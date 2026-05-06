"""
Redis Service
==============
Redis client wrapper for caching market data.
"""

import redis
import logging
from app.config import get_settings

logger = logging.getLogger(__name__)


def get_redis_client():
    """Get a Redis client. Returns None if Redis is not available."""
    settings = get_settings()
    try:
        client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            password=settings.REDIS_PASSWORD if settings.REDIS_PASSWORD else None,
            ssl=settings.REDIS_SSL,
            decode_responses=True,
            socket_timeout=5,
        )
        client.ping()
        logger.info("Redis connected successfully")
        return client
    except Exception as e:
        logger.warning(f"Redis not available, running without cache: {e}")
        return None
