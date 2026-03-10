"""POST /matrix/build — 대규모 매트릭스 생성"""

import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Header

from ..api_models import MatrixBuildRequest
from ..core.auth import verify_api_key, check_rate_limit
from ..core.dependencies import get_components
from .. import config

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "/matrix/build",
    tags=["매트릭스"],
    summary="OSRM 거리/시간 매트릭스 생성",
    description="""
좌표 목록 간의 거리(m)/시간(초) 매트릭스를 생성한다.

### 동작 방식
- OSRM Table API 사용
- 대규모 좌표(75+)는 75×75 청크로 분할하여 병렬 처리
- 소규모(<75)는 단일 OSRM 호출

### 응답
- `durations`: NxN 시간 매트릭스 (초 단위)
- `distances`: NxN 거리 매트릭스 (미터 단위)

### 인증
`X-API-Key` 헤더 필수.
""",
    responses={
        200: {"description": "매트릭스 생성 성공"},
        400: {"description": "좌표 누락 또는 형식 오류"},
        401: {"description": "API Key 누락"},
        500: {"description": "OSRM 연결 오류"},
    },
)
async def build_matrix(
    request_body: MatrixBuildRequest,
    x_api_key: Optional[str] = Header(None, description="API Key (필수)")
) -> Dict[str, Any]:
    verify_api_key(x_api_key)
    check_rate_limit(x_api_key)

    c = get_components()
    locations = request_body.locations
    profile = request_body.profile or "driving"

    if not locations:
        raise HTTPException(status_code=400, detail="locations required")

    try:
        result = await c.matrix_builder.build_matrix(locations, profile)
        return {
            "durations": result["durations"],
            "distances": result["distances"],
            "size": len(locations),
            "_metadata": {
                "chunk_size": config.OSRM_CHUNK_SIZE,
                "max_workers": config.OSRM_MAX_WORKERS,
            }
        }
    except Exception as e:
        logger.error(f"Matrix build failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
