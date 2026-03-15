"""비동기 Job 진행률 조회 엔드포인트"""

import logging
from fastapi import APIRouter, HTTPException

from celery.result import AsyncResult
from ..services.celery_app import celery_app

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get(
    "/jobs/{job_id}",
    tags=["HGLIS"],
    summary="비동기 배차 작업 진행률/결과 조회",
    description="""
`POST /dispatch?async=true`로 시작한 비동기 배차 작업의 진행률과 결과를 조회한다.

### 인증
불필요 (job_id만 있으면 조회 가능)

### 응답 구조
- `status`: `"processing"` / `"completed"` / `"failed"`
- `progress.stage`: 현재 단계
- `progress.percentage`: 진행률 (0~100)
- `result`: 완료 시 배차 결과 (HglisDispatchResponse)
- `error`: 실패 시 오류 메시지

### Celery 상태 매핑
| Celery 상태 | 응답 status | stage | % |
|-------------|-------------|-------|---|
| PENDING | processing | queued | 0 |
| STARTED | processing | optimizing | 50 |
| SUCCESS | completed | — | 100 |
| FAILURE | failed | — | — |

### 폴링 권장 간격
1~2초
""",
    responses={
        200: {"description": "작업 상태 조회 성공"},
        404: {"description": "job_id에 해당하는 작업 없음"},
    },
)
async def get_job_status(job_id: str):
    result = AsyncResult(job_id, app=celery_app)
    state = result.state

    if state == "PENDING":
        return {
            "job_id": job_id,
            "status": "processing",
            "progress": {"stage": "queued", "stage_label": "대기 중", "percentage": 0},
        }
    elif state == "STARTED":
        return {
            "job_id": job_id,
            "status": "processing",
            "progress": {"stage": "optimizing", "stage_label": "최적화 중", "percentage": 50},
        }
    elif state == "SUCCESS":
        return {
            "job_id": job_id,
            "status": "completed",
            "progress": {"stage": "completed", "stage_label": "완료", "percentage": 100},
            "result": result.get(),
        }
    elif state == "FAILURE":
        return {
            "job_id": job_id,
            "status": "failed",
            "progress": {"stage": "failed", "stage_label": "실패", "percentage": 100},
            "error": str(result.result),
        }
    else:
        # RETRY, REVOKED 등 기타 상태
        return {
            "job_id": job_id,
            "status": "processing",
            "progress": {"stage": state.lower(), "stage_label": state, "percentage": 30},
        }
