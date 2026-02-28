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


@router.post("/distribute")
async def distribute(request_body: DistributeRequest) -> Dict[str, Any]:
    """
    VROOM 호환 배차 엔드포인트

    VROOM 표준 JSON 포맷으로 입출력. API Key 불필요.
    Route Playground 및 외부 VROOM 호환 도구에서 직접 호출 가능.
    부가 기능: 미배정 작업에 대한 사유 분석(reasons)을 자동 포함.
    """
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
