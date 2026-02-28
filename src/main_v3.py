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
app = FastAPI(
    title="VROOM Wrapper v3.0",
    version="3.0.0",
    description="VRP optimization platform - Roouty Engine + Python Wrapper synthesis"
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
