#!/usr/bin/env python3
"""
VROOM Wrapper v3.0 - 정반합 (Synthesis)

Roouty Engine (Go) + Python Wrapper 통합:
- VROOM 바이너리 직접 호출 (vroom-express 제거)
- 2-Pass 최적화 (초기 배정 + 경로별 최적화)
- 도달 불가능 작업 사전 필터링
- 대규모 매트릭스 병렬 청킹
- 기존 v2.0 기능 전체 유지 (인증, 캐싱, 분석, 비즈니스 규칙)
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from . import config
from .core.dependencies import init_components, get_components
from .api import (
    distribute_router,
    optimize_router,
    matrix_router,
    map_matching_router,
    health_router,
    dispatch_router,
    jobs_router,
    valhalla_router,
)

# 로깅 설정
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL, logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================
# FastAPI 앱
# ============================================================
DESCRIPTION = """
## VROOM Wrapper v3.0 — VRP 최적화 플랫폼

VROOM C++ 바이너리를 직접 호출하는 Python FastAPI 래퍼.
OSRM 도로 라우팅, Redis 캐싱, 2-Pass 최적화를 지원한다.

### 주요 기능

- **VROOM 호환** (`/distribute`): VROOM 표준 JSON 그대로 사용. API Key 불필요.
- **최적화 파이프라인** (`/optimize`): 도달불가 필터 → 2-Pass 최적화 → 자동 재시도 → 분석
- **HGLIS 배차** (`/dispatch`): 가전 배송 전용. C1~C8 비즈니스 제약, 비동기 모드 지원.
- **매트릭스** (`/matrix/build`): OSRM 청크 매트릭스 (75x75 병렬).
- **맵 매칭** (`/map-matching`): GPS 궤적 도로 스냅.

### 인증

`X-API-Key` 헤더. 데모 키: `demo-key-12345`

| 인증 불필요 | 인증 필요 |
|------------|----------|
| `/distribute`, `/health`, `/`, `/jobs/{id}` | `/optimize`, `/dispatch`, `/matrix/build`, `/map-matching/match` |

### 처리 파이프라인 (2-Pass)

```
좌표 → OSRM 매트릭스 1회 → 도달불가 필터 → Pass1(배정) → Pass2(경로최적화) → 결과
```
"""

TAGS_METADATA = [
    {"name": "배차", "description": "VROOM 호환 및 HGLIS 배차 엔드포인트"},
    {"name": "최적화", "description": "VRP 최적화 파이프라인 (BASIC / STANDARD / PREMIUM)"},
    {"name": "HGLIS", "description": "HGLIS 가전 배송 배차 — C1~C8 비즈니스 제약 적용"},
    {"name": "매트릭스", "description": "OSRM 기반 거리/시간 매트릭스 생성"},
    {"name": "맵 매칭", "description": "GPS 궤적 도로 매칭 및 품질 검증"},
    {"name": "시스템", "description": "헬스 체크, 캐시, 서비스 정보"},
]

app = FastAPI(
    title="VROOM Wrapper v3.0",
    version="3.0.0",
    description=DESCRIPTION,
    openapi_tags=TAGS_METADATA,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# 라우터 등록
# ============================================================
app.include_router(distribute_router)
app.include_router(optimize_router)
app.include_router(matrix_router)
app.include_router(map_matching_router)
app.include_router(health_router)
app.include_router(dispatch_router)
app.include_router(jobs_router)
app.include_router(valhalla_router)


# ============================================================
# Startup / Shutdown
# ============================================================
@app.on_event("startup")
async def startup_event():
    """앱 시작 시 컴포넌트 초기화"""
    config.print_config()

    c = init_components()

    if c.controller.executor:
        logger.info("VROOM engine: direct binary call")
    else:
        logger.info(f"VROOM engine: HTTP fallback ({config.VROOM_URL})")

    if c.controller.two_pass_optimizer:
        logger.info("2-Pass optimizer: enabled")

    if c.controller.unreachable_filter:
        logger.info("Unreachable filter: enabled")

    logger.info(f"Map Matching engine: {config.OSRM_URL}")
    logger.info("VROOM Wrapper v3.0 started")


if __name__ == "__main__":
    import uvicorn

    logger.info("Starting VROOM Wrapper v3.0...")

    uvicorn.run(
        app,
        host=config.HOST,
        port=config.PORT,
        log_level=config.LOG_LEVEL.lower()
    )
