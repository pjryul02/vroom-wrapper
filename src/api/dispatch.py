"""POST /dispatch — HGLIS 배차 엔드포인트"""

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Header, Query

from ..core.auth import verify_api_key, check_rate_limit
from ..core.dependencies import get_components
from ..hglis.models import HglisDispatchRequest, HglisDispatchResponse
from ..hglis.dispatcher import HglisDispatcher
from ..services.celery_tasks import dispatch_task

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "/dispatch",
    tags=["HGLIS"],
    summary="HGLIS 가전 배송 배차",
    description="""
HGLIS(가전 배송 물류) 전용 배차 엔드포인트.
HGLIS 비즈니스 모델(기사, 오더, 제품, 스케줄)을 입력하면 최적 배차 결과를 반환한다.

### 처리 파이프라인
1. **입력 검증**: 좌표, 권역코드, 제품 정합성
2. **스킬 인코딩**: 기능도(C1), 인원(crew), 시간대 → VROOM skills로 변환
3. **VROOM 조립**: HGLIS → VROOM 표준 JSON 변환
4. **OSRM 매트릭스**: 모든 좌표의 거리/시간 매트릭스 1회 계산
5. **도달불가 필터**: 매트릭스 기반 도달 불가능 오더 제거
6. **2-Pass 최적화**: Pass1(배정) → Pass2(경로별 순서 최적화)
7. **C2/C6 검증**: 설치비 하한(C2), 월 수익 상한(C6) 사후 검증
8. **결과 변환**: VROOM 결과 → HGLIS 응답 (배송순서, 도착시각, 기사요약)

### 비즈니스 제약 (자동 적용)
| 코드 | 제약 | 설명 |
|------|------|------|
| C1 | 기능도 | 제품 required_grade ≤ 기사 skill_grade |
| C2 | 설치비 하한 | 기사 월 최소 수익 보장 |
| C3 | 적재 용량 | 오더 CBM 합 ≤ 기사 capacity_cbm |
| C4 | 배송 건수 | 기사 당 max_tasks_per_driver 제한 |
| C5 | 시간대 | preferred_time_slot 기반 배송 시간 |
| C6 | 수익 상한 | 월 수익 상한 (S:1200만/A:1100만/B:900만/C:700만) |
| C7 | 신제품 | new_product_restricted 기사에게 신제품 미배정 |
| C8 | 미결 이력 | avoid_models 해당 모델 미배정 |

### 비동기 모드
`?async=true` 쿼리 파라미터로 비동기 실행.
- 즉시 `job_id` 반환
- `GET /jobs/{job_id}`로 진행률 조회 (0%~100%)
- 대량 배차(50건+) 시 권장

### 권역 모드
- `strict`: 기사-오더 권역 정확 일치 (기본)
- `flexible`: 인접 권역 허용
- `ignore`: 권역 무시, 전체 매칭
""",
    responses={
        200: {"description": "배차 성공 (results, driver_summary, unassigned, warnings 포함)"},
        400: {"description": "검증 실패 (모든 오더가 제약 위반 등)"},
        401: {"description": "API Key 누락 또는 유효하지 않음"},
        422: {"description": "입력 형식 오류 (권역코드, 좌표 범위, 필수 필드 등)"},
        429: {"description": "요청률 제한 초과"},
        500: {"description": "내부 오류"},
    },
)
async def dispatch(
    request_body: HglisDispatchRequest,
    x_api_key: Optional[str] = Header(None, description="API Key (필수). 데모: demo-key-12345"),
    async_mode: bool = Query(False, alias="async", description="true: 비동기 모드 (job_id 즉시 반환)"),
):
    verify_api_key(x_api_key)
    check_rate_limit(x_api_key)

    if async_mode:
        # 비동기 모드: Celery 큐에 submit, task ID 즉시 반환
        result = dispatch_task.delay(request_body.model_dump())
        return {
            "job_id": result.id,
            "status": "queued",
            "poll_url": f"/jobs/{result.id}",
        }

    # 동기 모드: 기존 동작
    try:
        c = get_components()
        dispatcher = HglisDispatcher(
            controller=c.controller,
            valhalla_eta_updater=c.valhalla_eta_updater,  # Pass 3: ETA 업데이터 주입
        )
        response = await dispatcher.dispatch(request_body)

        if response.status == "failed" and "검증 실패" in response.meta.get("error", ""):
            raise HTTPException(status_code=400, detail=response.meta)

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"/dispatch 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
