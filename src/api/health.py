"""GET /health, GET /, DELETE /cache/clear"""

import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, Header

from ..core.auth import verify_api_key
from ..core.dependencies import get_components
from .. import config

logger = logging.getLogger(__name__)
router = APIRouter()


@router.delete(
    "/cache/clear",
    tags=["시스템"],
    summary="결과 캐시 전체 삭제",
    description="""
Redis(또는 인메모리) 캐시에 저장된 최적화 결과를 모두 삭제한다.

### 용도
- 좌표/제약 변경 후 이전 캐시 결과가 반환되는 것을 방지
- 디버깅 시 항상 최신 결과 확인

### 인증
`X-API-Key` 헤더 필수.
""",
    responses={
        200: {"description": "캐시 삭제 성공"},
        401: {"description": "API Key 누락 또는 유효하지 않음"},
    },
)
async def clear_cache(x_api_key: Optional[str] = Header(None, description="API Key (필수)")):
    """캐시 전체 삭제"""
    verify_api_key(x_api_key)
    c = get_components()
    c.cache_manager.clear()
    return {"message": "Cache cleared successfully"}


@router.get(
    "/health",
    tags=["시스템"],
    summary="서비스 헬스 체크",
    description="""
VROOM Wrapper 전체 컴포넌트 상태를 반환한다.

### 응답 필드
- `engine`: `direct`(바이너리) 또는 `http`(VROOM 서버)
- `components`: 각 컴포넌트 상태
  - `vroom_binary`: `healthy` / `unhealthy` / `http_fallback`
  - `two_pass`: `enabled` / `disabled`
  - `unreachable_filter`: `enabled` / `disabled`
  - `cache`: `redis` / `memory`

### 인증
불필요.
""",
)
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


@router.get(
    "/",
    tags=["시스템"],
    summary="서비스 정보 및 엔드포인트 목록",
    description="VROOM Wrapper 버전, 사용 가능한 엔드포인트, 데모 API 키를 반환한다. 인증 불필요.",
)
async def root():
    """루트 엔드포인트"""
    return {
        "service": "VROOM Wrapper v3.0 - Synthesis Edition",
        "version": "3.0.0",
        "architecture": "Roouty Engine (Go) + Python Wrapper synthesis",
        "endpoints": {
            "distribute":             "POST /distribute (VROOM+OSRM, no API Key)",
            "optimize_basic":         "POST /optimize/basic (VROOM+OSRM BASIC, requires API Key)",
            "optimize":               "POST /optimize (VROOM+OSRM STANDARD, requires API Key)",
            "optimize_premium":       "POST /optimize/premium (VROOM+OSRM PREMIUM 3-scenario, requires API Key)",
            "valhalla_distribute":    "POST /valhalla/distribute (VROOM+Valhalla, no API Key)",
            "valhalla_optimize_basic":"POST /valhalla/optimize/basic (VROOM+Valhalla BASIC, requires API Key)",
            "valhalla_optimize":      "POST /valhalla/optimize (VROOM+Valhalla STANDARD, requires API Key)",
            "valhalla_optimize_premium":"POST /valhalla/optimize/premium (VROOM+Valhalla PREMIUM, requires API Key)",
            "dispatch":               "POST /dispatch (HGLIS 가전배차 C1~C8, requires API Key)",
            "matrix_build":           "POST /matrix/build (chunked OSRM matrix)",
            "map_matching":           "POST /map-matching/match (GPS trajectory matching)",
            "map_matching_health":    "GET /map-matching/health",
            "map_matching_validate":  "POST /map-matching/validate",
            "clear_cache":            "DELETE /cache/clear",
            "health":                 "GET /health",
            "swagger_ui":             "GET /docs (Swagger UI)",
        },
        "authentication": "Required for optimize/dispatch endpoints (Header: X-API-Key)",
        "demo_api_key": "demo-key-12345",
    }
