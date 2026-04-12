import json
import hashlib
import logging
from typing import Any, Optional
import redis.asyncio as redis
from app.config import settings

logger = logging.getLogger(__name__)

class CacheService:
    def __init__(self):
        self._redis: Optional[redis.Redis] = None
        self.enabled = bool(settings.REDIS_URL)

    async def get_redis(self) -> Optional[redis.Redis]:
        if not self.enabled:
            return None
        if self._redis is None:
            try:
                self._redis = redis.from_url(
                    settings.REDIS_URL, 
                    decode_responses=True,
                    socket_timeout=5.0
                )
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")
                self.enabled = False
        return self._redis

    def _generate_key(self, prefix: str, data: str) -> str:
        sha = hashlib.sha256(data.encode()).hexdigest()
        return f"patentiq:{prefix}:{sha}"

    async def get_embedding(self, text: str) -> Optional[list[float]]:
        r = await self.get_redis()
        if not r:
            return None
        
        key = self._generate_key("emb", text)
        try:
            cached = await r.get(key)
            if cached:
                return json.loads(cached)
        except Exception as e:
            logger.warning(f"Cache get_embedding failed: {e}")
        return None

    async def set_embedding(self, text: str, embedding: list[float], ttl: int = 604800):
        # Default TTL 7 days for embeddings as they are deterministic
        r = await self.get_redis()
        if not r:
            return
        
        key = self._generate_key("emb", text)
        try:
            await r.set(key, json.dumps(embedding), ex=ttl)
        except Exception as e:
            logger.warning(f"Cache set_embedding failed: {e}")

    async def get_llm_response(self, prompt: str) -> Optional[str]:
        r = await self.get_redis()
        if not r:
            return None
        
        key = self._generate_key("llm", prompt)
        try:
            return await r.get(key)
        except Exception as e:
            logger.warning(f"Cache get_llm_response failed: {e}")
        return None

    async def set_llm_response(self, prompt: str, response: str, ttl: int = 86400):
        # Default TTL 24 hours for LLM responses
        r = await self.get_redis()
        if not r:
            return
        
        key = self._generate_key("llm", prompt)
        try:
            await r.set(key, response, ex=ttl)
        except Exception as e:
            logger.warning(f"Cache set_llm_response failed: {e}")
 
    async def acquire_llm_semaphore(self, limit: int = 15) -> bool:
        """
        Try to acquire a slot for an LLM request. 
        Returns True if successful, False if at limit.
        """
        r = await self.get_redis()
        if not r:
            return True # Fail open if Redis is down
        
        key = "patentiq:llm_concurrency_count"
        try:
            # Atomic increment
            count = await r.incr(key)
            if count > limit:
                await r.decr(key)
                return False
            return True
        except Exception as e:
            logger.warning(f"Semaphore acquire failed: {e}")
            return True

    async def release_llm_semaphore(self):
        """Release a slot."""
        r = await self.get_redis()
        if not r:
            return
        
        key = "patentiq:llm_concurrency_count"
        try:
            await r.decr(key)
            # Ensure it doesn't go below 0 (self-healing)
            count = int(await r.get(key) or 0)
            if count < 0:
                await r.set(key, 0)
        except Exception as e:
            logger.warning(f"Semaphore release failed: {e}")

cache_service = CacheService()
