"""비동기 Job 진행률 조회 엔드포인트"""

import logging
from fastapi import APIRouter, HTTPException

from ..services.job_manager import get_job_manager

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

### 진행 단계
| stage | % | 설명 |
|-------|---|------|
| queued | 0 | 대기 중 |
| validating | 10 | 입력 검증 |
| preprocessing | 20 | 전처리 (매트릭스, 필터) |
| optimizing | 40 | Pass 1 최적화 |
| optimizing_pass2 | 60 | Pass 2 최적화 |
| retry_relaxation | 75 | 제약 완화 재시도 |
| postprocessing | 90 | 후처리 (C2/C6) |
| completed | 100 | 완료 |

### 폴링 권장 간격
1~2초
""",
    responses={
        200: {"description": "작업 상태 조회 성공"},
        404: {"description": "job_id에 해당하는 작업 없음"},
    },
)
async def get_job_status(job_id: str):
    jm = get_job_manager()
    job = jm.get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    return job.to_dict()
