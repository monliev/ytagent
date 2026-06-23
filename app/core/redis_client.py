import redis.asyncio as aioredis
from app.core.config import settings

# Async Redis connection client for locks, session data, and transient flags
redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
