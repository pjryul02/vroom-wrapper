"""POST /distribute — VROOM 호환 배차 엔드포인트 (API Key 불필요)"""

import time
import logging
from typing import Dict, Any
from fastapi import APIRouter

from ..api_models import DistributeRequest
from ..postprocessing import ConstraintChecker
from ..core.dependencies import get_components
from .. import config

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "/distribute",
    tags=["배차"],
    summary="VROOM 호환 배차 (인증 불필요)",
    description="""
VROOM 표준 JSON 포맷을 그대로 사용하는 범용 배차 엔드포인트.

**인증 불필요** — Route Playground, Postman 등 외부 도구에서 바로 호출 가능.

### 동작 방식
- VROOM C++ 바이너리를 직접 호출 (subprocess)
- OSRM을 통해 도로 기반 거리/시간 계산
- geometry를 내부적으로 항상 요청하되, 클라이언트가 `options.g=true`를 명시한 경우에만 응답에 포함

### Wrapper 추가 필드
- `unassigned[].reasons`: 미배정 사유 자동 분석 (skills, capacity, time_window 등)
- `_wrapper`: 래퍼 메타데이터 (버전, 엔진, 처리시간)

### 참고
- 2-Pass 최적화, 도달불가 필터 등 고급 파이프라인은 `/optimize` 사용
- HGLIS 비즈니스 제약은 `/dispatch` 사용
""",
    responses={
        200: {"description": "최적화 성공 (VROOM 표준 응답 + reasons + _wrapper)"},
        422: {"description": "입력 검증 실패 (vehicles/jobs 누락 등)"},
        500: {"description": "VROOM 바이너리 실행 오류"},
    },
)
async def distribute(request_body: DistributeRequest) -> Dict[str, Any]:
    c = get_components()
    start_time = time.time()
    vrp_data = request_body.model_dump(exclude_none=True)

    try:
        options = vrp_data.get('options', {})
        user_requested_geometry = options.get('g', False)

        if c.controller.executor:
            result = await c.controller.executor.execute(
                vrp_data,
                geometry=True,
            )
        else:
            import httpx
            async with httpx.AsyncClient(timeout=300.0) as client:
                resp = await client.post(config.VROOM_URL, json=vrp_data)
                resp.raise_for_status()
                result = resp.json()

        # 미배정 사유 분석
        if result.get('unassigned'):
            try:
                checker = ConstraintChecker(vrp_data)
                reasons_map = checker.analyze_unassigned(result['unassigned'])
                for u in result['unassigned']:
                    job_id = u.get('id')
                    if job_id in reasons_map:
                        u['reasons'] = reasons_map[job_id]
            except Exception:
                pass

        if not user_requested_geometry:
            for route in result.get('routes', []):
                route.pop('geometry', None)

        if 'code' not in result:
            result['code'] = 0

        processing_time = int((time.time() - start_time) * 1000)
        result['_wrapper'] = {
            'version': '3.0.0',
            'engine': 'direct' if c.controller.executor else 'http',
            'processing_time_ms': processing_time,
        }

        return result

    except Exception as e:
        logger.error(f"/distribute failed: {e}")
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=str(e))
