#!/usr/bin/env python3
"""
VROOM Wrapper v2.0 - Main Application

Complete VRP optimization platform with:
- Phase 1: Pre-processing (validation, normalization, business rules)
- Phase 2: Control (config management, constraint tuning, multi-scenario)
- Phase 3: Post-processing (quality analysis, suggestions)
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any, Optional
import logging

# Phase 1: Pre-processing
from preprocessing import PreProcessor

# Phase 2: Control
from control import OptimizationController, ControlLevel

# Phase 3: Post-processing
from postprocessing import ResultAnalyzer

# v1.0 미배정 사유 분석 (통합)
import sys
sys.path.append('..')
from vroom_wrapper import ConstraintChecker

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# FastAPI 앱
app = FastAPI(
    title="VROOM Wrapper v2.0",
    version="2.0.0",
    description="Complete VRP optimization platform"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 컴포넌트 초기화
preprocessor = PreProcessor()
controller = OptimizationController(vroom_url="http://localhost:3000")
analyzer = ResultAnalyzer()


@app.post("/optimize")
async def optimize_vrp(
    request_body: Dict[str, Any]
) -> Dict[str, Any]:
    """
    VRP 최적화 (STANDARD 레벨)

    전체 파이프라인:
    1. 입력 검증 및 정규화
    2. 비즈니스 규칙 적용
    3. VROOM 최적화
    4. 미배정 사유 분석 (v1.0)
    5. 품질 분석 및 제안

    Request Body:
        {
            "vehicles": [...],
            "jobs": [...],
            "business_rules": {...}  # optional
        }

    Returns:
        VROOM 결과 + 분석 리포트
    """
    try:
        logger.info("Received optimization request (STANDARD level)")

        # Phase 1: Pre-processing
        business_rules = request_body.pop('business_rules', None)
        vrp_input = preprocessor.process(request_body, business_rules)

        # Phase 2: Optimization
        vroom_result = await controller.optimize(
            vrp_input,
            control_level=ControlLevel.STANDARD
        )

        # v1.0: 미배정 사유 분석
        if vroom_result.get('unassigned'):
            checker = ConstraintChecker(vrp_input)
            reasons_map = checker.analyze_unassigned(vroom_result['unassigned'])

            # 결과에 사유 추가
            for unassigned in vroom_result['unassigned']:
                job_id = unassigned['id']
                if job_id in reasons_map:
                    unassigned['reasons'] = reasons_map[job_id]

        # Phase 3: Post-processing
        analysis = analyzer.analyze(vrp_input, vroom_result)

        # 최종 응답
        response = vroom_result.copy()
        response['analysis'] = analysis
        response['wrapper_version'] = '2.0.0'

        logger.info(f"Optimization complete (quality score: {analysis['quality_score']})")

        return response

    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Optimization failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/optimize/basic")
async def optimize_basic(request_body: Dict[str, Any]) -> Dict[str, Any]:
    """BASIC 레벨 최적화 (빠른 최적화)"""
    try:
        vrp_input = preprocessor.process(request_body)
        vroom_result = await controller.optimize(
            vrp_input,
            control_level=ControlLevel.BASIC
        )

        return vroom_result

    except Exception as e:
        logger.error(f"BASIC optimization failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/optimize/premium")
async def optimize_premium(request_body: Dict[str, Any]) -> Dict[str, Any]:
    """PREMIUM 레벨 최적화 (다중 시나리오)"""
    try:
        vrp_input = preprocessor.process(request_body)

        # 다중 시나리오 활성화
        premium_controller = OptimizationController(
            vroom_url="http://localhost:3000",
            enable_multi_scenario=True
        )

        vroom_result = await premium_controller.optimize(
            vrp_input,
            control_level=ControlLevel.PREMIUM
        )

        # 분석
        analysis = analyzer.analyze(vrp_input, vroom_result)
        vroom_result['analysis'] = analysis

        return vroom_result

    except Exception as e:
        logger.error(f"PREMIUM optimization failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    """헬스 체크"""
    return {
        "status": "healthy",
        "version": "2.0.0",
        "components": {
            "preprocessor": "ready",
            "controller": "ready",
            "analyzer": "ready"
        }
    }


@app.get("/")
async def root():
    """루트 엔드포인트"""
    return {
        "service": "VROOM Wrapper v2.0",
        "version": "2.0.0",
        "endpoints": {
            "optimize": "POST /optimize (STANDARD)",
            "optimize_basic": "POST /optimize/basic (BASIC)",
            "optimize_premium": "POST /optimize/premium (PREMIUM)",
            "health": "GET /health"
        },
        "features": [
            "Input validation & normalization",
            "Business rules (VIP/urgent/region)",
            "Multi-level optimization (BASIC/STANDARD/PREMIUM)",
            "Constraint relaxation & auto-retry",
            "Multi-scenario optimization",
            "Unassigned reason analysis (v1.0)",
            "Quality scoring & suggestions"
        ]
    }


if __name__ == "__main__":
    import uvicorn

    logger.info("Starting VROOM Wrapper v2.0...")

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
