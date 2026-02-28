"""GET /health, GET /, DELETE /cache/clear"""

import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, Header

from ..core.auth import verify_api_key
from ..core.dependencies import get_components
from .. import config

logger = logging.getLogger(__name__)
router = APIRouter()


@router.delete("/cache/clear")
async def clear_cache(x_api_key: Optional[str] = Header(None)):
    """캐시 전체 삭제"""
    verify_api_key(x_api_key)
    c = get_components()
    c.cache_manager.clear()
    return {"message": "Cache cleared successfully"}


@router.get("/health")
async def health_check():
    """헬스 체크 (v3.0 - VROOM 바이너리 상태 포함)"""
    c = get_components()
    vroom_status = "unknown"

    if c.controller.executor:
        try:
            healthy = await c.controller.executor.health_check()
            vroom_status = "healthy" if healthy else "unhealthy"
        except Exception:
            vroom_status = "error"
    else:
        vroom_status = "http_fallback"

    return {
        "status": "healthy",
        "version": "3.0.0",
        "engine": "direct" if config.USE_DIRECT_CALL else "http",
        "components": {
            "preprocessor": "ready",
            "controller": "ready",
            "analyzer": "ready",
            "statistics": "ready",
            "cache": "memory" if not c.cache_manager.redis_client else "redis",
            "vroom_binary": vroom_status,
            "two_pass": "enabled" if c.controller.two_pass_optimizer else "disabled",
            "unreachable_filter": "enabled" if c.controller.unreachable_filter else "disabled",
            "matrix_chunking": "ready",
            "map_matching": "ready",
        }
    }


@router.get("/")
async def root():
    """루트 엔드포인트"""
    return {
        "service": "VROOM Wrapper v3.0 - Synthesis Edition",
        "version": "3.0.0",
        "architecture": "Roouty Engine (Go) + Python Wrapper synthesis",
        "endpoints": {
            "distribute": "POST /distribute (VROOM-compatible, no API Key)",
            "optimize": "POST /optimize (STANDARD, requires API Key)",
            "optimize_basic": "POST /optimize/basic (BASIC, requires API Key)",
            "optimize_premium": "POST /optimize/premium (PREMIUM, requires API Key)",
            "matrix_build": "POST /matrix/build (v3.0 chunked matrix)",
            "map_matching": "POST /map-matching/match (GPS trajectory matching)",
            "map_matching_health": "GET /map-matching/health (OSRM status)",
            "map_matching_validate": "POST /map-matching/validate (trajectory validation)",
            "clear_cache": "DELETE /cache/clear",
            "health": "GET /health"
        },
        "authentication": "Required (Header: X-API-Key)",
        "demo_api_key": "demo-key-12345",
    }
