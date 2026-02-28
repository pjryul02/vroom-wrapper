"""POST /dispatch — HGLIS 배차 엔드포인트"""

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Header

from ..core.auth import verify_api_key, check_rate_limit
from ..core.dependencies import get_components
from ..hglis.models import HglisDispatchRequest, HglisDispatchResponse
from ..hglis.dispatcher import HglisDispatcher

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/dispatch", response_model=HglisDispatchResponse)
async def dispatch(
    request_body: HglisDispatchRequest,
    x_api_key: Optional[str] = Header(None),
) -> HglisDispatchResponse:
    """
    HGLIS 배차 엔드포인트

    C1~C8 제약조건 기반 VRP 최적화:
    - C3 시간윈도우, C4 기능도, C5 CBM, C7 신제품, C8 미결이력 → VROOM skills/time_windows/capacity
    - VROOM 바이너리 직접 호출
    - 결과를 HGLIS 응답 형식으로 변환
    """
    verify_api_key(x_api_key)
    check_rate_limit(x_api_key)

    try:
        c = get_components()
        dispatcher = HglisDispatcher(controller=c.controller)
        response = await dispatcher.dispatch(request_body)

        if response.status == "failed" and "검증 실패" in response.meta.get("error", ""):
            raise HTTPException(status_code=400, detail=response.meta)

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"/dispatch 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
