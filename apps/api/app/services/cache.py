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

cache_service = CacheService()
