#!/usr/bin/env python3
"""
CacheManager - Redis 기반 캐싱

Phase 5: 성능 최적화
"""

from typing import Dict, Any, Optional
import hashlib
import json
import logging

logger = logging.getLogger(__name__)


class CacheManager:
    """Redis 기반 결과 캐싱 (Redis 없으면 메모리 캐시)"""

    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url
        self.redis_client = None
        self.memory_cache = {}  # Fallback

        if redis_url:
            try:
                import redis
                self.redis_client = redis.from_url(redis_url, decode_responses=True)
                self.redis_client.ping()
                logger.info(f"✓ Redis connected: {redis_url}")
            except Exception as e:
                logger.warning(f"Redis connection failed: {e}, using memory cache")

    def _generate_key(self, vrp_input: Dict[str, Any]) -> str:
        """VRP 입력에서 캐시 키 생성"""
        # 정렬된 JSON으로 해시 생성
        normalized = json.dumps(vrp_input, sort_keys=True)
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]

    def get(self, vrp_input: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """캐시에서 결과 조회"""
        key = self._generate_key(vrp_input)

        try:
            if self.redis_client:
                cached = self.redis_client.get(f"vroom:{key}")
                if cached:
                    logger.info(f"✓ Cache hit (Redis): {key}")
                    return json.loads(cached)
            else:
                if key in self.memory_cache:
                    logger.info(f"✓ Cache hit (Memory): {key}")
                    return self.memory_cache[key]
        except Exception as e:
            logger.error(f"Cache get error: {e}")

        return None

    def set(
        self,
        vrp_input: Dict[str, Any],
        result: Dict[str, Any],
        ttl: int = 3600
    ):
        """결과를 캐시에 저장"""
        key = self._generate_key(vrp_input)

        try:
            if self.redis_client:
                self.redis_client.setex(
                    f"vroom:{key}",
                    ttl,
                    json.dumps(result)
                )
                logger.debug(f"✓ Cached to Redis: {key} (TTL: {ttl}s)")
            else:
                self.memory_cache[key] = result
                logger.debug(f"✓ Cached to Memory: {key}")
        except Exception as e:
            logger.error(f"Cache set error: {e}")

    def clear(self):
        """캐시 전체 삭제"""
        try:
            if self.redis_client:
                keys = self.redis_client.keys("vroom:*")
                if keys:
                    self.redis_client.delete(*keys)
                logger.info(f"✓ Cleared {len(keys)} cache entries (Redis)")
            else:
                count = len(self.memory_cache)
                self.memory_cache.clear()
                logger.info(f"✓ Cleared {count} cache entries (Memory)")
        except Exception as e:
            logger.error(f"Cache clear error: {e}")
