"""
Valhalla 라우팅 기반 엔드포인트

OSRM 대신 Valhalla를 라우팅 백엔드로 사용하는 동일한 API 집합.

엔드포인트:
  POST /valhalla/distribute       — VROOM 호환, 인증 불필요
  POST /valhalla/optimize         — 전처리 + Valhalla 매트릭스 + STANDARD 최적화
  POST /valhalla/optimize/basic   — 경량 최적화
  POST /valhalla/optimize/premium — 2-Pass 최적화

차이점 (vs OSRM 엔드포인트):
  - VROOM에 -r valhalla -a car:{host} -p car:{port} 플래그 전달
  - 매트릭스 사전 계산: OSRM Table API → Valhalla sources_to_targets
  - Geometry: VROOM이 Valhalla /route 로 실제 도로선 획득
"""

import time
import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Header

from ..api_models import DistributeRequest, OptimizeRequest
from ..postprocessing import ConstraintChecker
from ..optimization.two_pass import TwoPassOptimizer
from ..core.auth import verify_api_key, check_rate_limit
from ..core.dependencies import get_components
from .. import config

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/valhalla", tags=["Valhalla"])


def _analyze_unassigned(vrp_input: dict, result: dict):
    """미배정 사유 분석 공통 로직"""
    if not result.get("unassigned"):
        return
    try:
        checker = ConstraintChecker(vrp_input)
        reasons_map = checker.analyze_unassigned(result["unassigned"])
        for u in result["unassigned"]:
            job_id = u.get("id")
            if job_id in reasons_map:
                u["reasons"] = reasons_map[job_id]
    except Exception:
        pass


def _require_valhalla(c):
    """Valhalla executor 존재 확인. 없으면 503."""
    if not c.valhalla_executor:
        raise HTTPException(
            status_code=503,
            detail=(
                "Valhalla engine is not available. "
                "Check VALHALLA_URL config and that valhalla-server container is running."
            ),
        )


def _patch_valhalla_profiles(vrp_data: dict) -> dict:
    """Valhalla용 vehicle profile 패치: car → auto (Valhalla costing method)"""
    for v in vrp_data.get("vehicles", []):
        if v.get("profile", "car") == "car":
            v["profile"] = "auto"
    return vrp_data


# ═══════════════════════════════════════════════════════════════════════════════
# POST /valhalla/distribute
# ═══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/distribute",
    summary="Valhalla 배차 (인증 불필요)",
    description="""
VROOM 표준 JSON 포맷 + Valhalla 라우팅 백엔드.

OSRM `/distribute`와 동일한 입/출력 포맷. 인증 불필요.

Valhalla가 실제 도로 기반 매트릭스·경로를 직접 계산.
""",
)
async def valhalla_distribute(request_body: DistributeRequest) -> Dict[str, Any]:
    c = get_components()
    _require_valhalla(c)

    start_time = time.time()
    vrp_data = request_body.model_dump(exclude_none=True)
    _patch_valhalla_profiles(vrp_data)

    try:
        options = vrp_data.get("options", {})
        user_requested_geometry = options.get("g", False)

        result = await c.valhalla_executor.execute(vrp_data, geometry=True)

        _analyze_unassigned(vrp_data, result)

        if not user_requested_geometry:
            for route in result.get("routes", []):
                route.pop("geometry", None)

        if "code" not in result:
            result["code"] = 0

        processing_time = int((time.time() - start_time) * 1000)
        result["_wrapper"] = {
            "version": "3.0.0",
            "engine": "valhalla",
            "processing_time_ms": processing_time,
        }
        return result

    except Exception as e:
        logger.error(f"/valhalla/distribute failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# POST /valhalla/optimize  (STANDARD)
# ═══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/optimize",
    summary="Valhalla STANDARD 최적화",
    description="""
전처리 → Valhalla 매트릭스 사전 계산 → 도달불가 필터 → VROOM 최적화

Valhalla `sources_to_targets` API로 실도로 매트릭스 선계산 후 VROOM에 주입.
미배정 자동 재시도 포함.

인증: `X-API-Key` 헤더 필수.
""",
)
async def valhalla_optimize_standard(
    request_body: OptimizeRequest,
    x_api_key: Optional[str] = Header(None),
) -> Dict[str, Any]:
    api_key_info = verify_api_key(x_api_key)
    check_rate_limit(x_api_key)

    c = get_components()
    _require_valhalla(c)
    start_time = time.time()

    try:
        use_cache = request_body.use_cache if request_body.use_cache is not None else True
        vrp_data = request_body.model_dump(exclude_none=True)
        vrp_data.pop("use_cache", None)
        vrp_data.pop("business_rules", None)
        _patch_valhalla_profiles(vrp_data)

        # 캐시 확인
        if use_cache:
            cached = c.cache_manager.get(vrp_data)
            if cached:
                cached["_metadata"] = {"from_cache": True, "engine": "valhalla"}
                return cached

        # 1. 전처리 (검증 + 정규화 + 비즈니스 규칙)
        vrp_input = await c.preprocessor.process(vrp_data)

        # 2. Valhalla 매트릭스 사전 계산 + VROOM 입력에 주입
        #    (UnreachableFilter 동작, 2-Pass 매트릭스 재사용 가능)
        if c.valhalla_preparer:
            vrp_input = await c.valhalla_preparer.prepare(vrp_input)

        # 3. 도달 불가능 필터
        unreachable_jobs = []
        if c.controller.unreachable_filter and vrp_input.get("matrices"):
            vrp_input, unreachable_jobs = c.controller.unreachable_filter.filter(vrp_input)

        # 4. VROOM + Valhalla 실행
        result = await c.valhalla_executor.execute(vrp_input, geometry=True)

        # 4a. 미배정 자동 재시도
        if result.get("unassigned"):
            retryable = [u for u in result["unassigned"] if u.get("reason") != "unreachable"]
            if retryable:
                result = await _retry_valhalla(c, vrp_input, result)

        if unreachable_jobs:
            result.setdefault("unassigned", []).extend(unreachable_jobs)
            result.setdefault("summary", {})["unassigned"] = len(result["unassigned"])

        _analyze_unassigned(vrp_input, result)

        # 5. 분석 + 통계
        analysis   = c.analyzer.analyze(vrp_input, result)
        statistics = c.stats_generator.generate(vrp_input, result)

        processing_time = int((time.time() - start_time) * 1000)
        response = {
            "wrapper_version": "3.0.0",
            "routes":     result.get("routes", []),
            "summary":    result.get("summary", {}),
            "unassigned": result.get("unassigned", []),
            "analysis":   analysis,
            "statistics": statistics,
            "_metadata": {
                "api_key":           api_key_info["name"],
                "control_level":     "STANDARD",
                "engine":            "valhalla",
                "processing_time_ms": processing_time,
                "from_cache":        False,
            },
        }

        if use_cache:
            c.cache_manager.set(vrp_data, response, ttl=3600)

        return response

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"/valhalla/optimize failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# POST /valhalla/optimize/basic
# ═══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/optimize/basic",
    summary="Valhalla BASIC 최적화",
    description="분석·통계·재시도 생략. 빠른 결과. 인증 필요.",
)
async def valhalla_optimize_basic(
    request_body: OptimizeRequest,
    x_api_key: Optional[str] = Header(None),
) -> Dict[str, Any]:
    api_key_info = verify_api_key(x_api_key)
    check_rate_limit(x_api_key)

    c = get_components()
    _require_valhalla(c)

    try:
        vrp_data = request_body.model_dump(exclude_none=True)
        vrp_data.pop("use_cache", None)
        vrp_data.pop("business_rules", None)
        _patch_valhalla_profiles(vrp_data)

        vrp_input = await c.preprocessor.process(vrp_data)

        if c.valhalla_preparer:
            vrp_input = await c.valhalla_preparer.prepare(vrp_input)

        result = await c.valhalla_executor.execute(vrp_input, geometry=True)
        _analyze_unassigned(vrp_input, result)

        return {
            "wrapper_version": "3.0.0",
            "routes":     result.get("routes", []),
            "summary":    result.get("summary", {}),
            "unassigned": result.get("unassigned", []),
            "_metadata": {"api_key": api_key_info["name"], "engine": "valhalla", "control_level": "BASIC"},
        }

    except Exception as e:
        logger.error(f"/valhalla/optimize/basic failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# POST /valhalla/optimize/premium
# ═══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/optimize/premium",
    summary="Valhalla PREMIUM 최적화 (2-Pass)",
    description="""
Valhalla 매트릭스 선계산 + 2-Pass 최적화 (10개 이상 job 시 활성).

인증: `X-API-Key` (Premium 권한) 필요. 요청률 50/시간.
""",
)
async def valhalla_optimize_premium(
    request_body: OptimizeRequest,
    x_api_key: Optional[str] = Header(None),
) -> Dict[str, Any]:
    api_key_info = verify_api_key(x_api_key)

    if "premium" not in api_key_info.get("features", []):
        raise HTTPException(status_code=403, detail="Premium feature not available")

    check_rate_limit(x_api_key, limit=50)

    c = get_components()
    _require_valhalla(c)
    start_time = time.time()

    try:
        vrp_data = request_body.model_dump(exclude_none=True)
        vrp_data.pop("use_cache", None)
        vrp_data.pop("business_rules", None)
        _patch_valhalla_profiles(vrp_data)

        vrp_input = await c.preprocessor.process(vrp_data)

        if c.valhalla_preparer:
            vrp_input = await c.valhalla_preparer.prepare(vrp_input)

        num_jobs = len(vrp_input.get("jobs", [])) + len(vrp_input.get("shipments", []))

        if num_jobs >= 10:
            # 2-Pass: Valhalla executor를 그대로 재사용
            two_pass = TwoPassOptimizer(
                executor=c.valhalla_executor,
                max_workers=config.TWO_PASS_MAX_WORKERS,
                initial_threads=config.TWO_PASS_INITIAL_THREADS,
                route_threads=config.TWO_PASS_ROUTE_THREADS,
            )
            result = await two_pass.optimize(vrp_input, geometry=True)
        else:
            result = await c.valhalla_executor.execute(vrp_input, geometry=True)

        _analyze_unassigned(vrp_input, result)
        analysis   = c.analyzer.analyze(vrp_input, result)
        statistics = c.stats_generator.generate(vrp_input, result)
        processing_time = int((time.time() - start_time) * 1000)

        return {
            "wrapper_version": "3.0.0",
            "routes":     result.get("routes", []),
            "summary":    result.get("summary", {}),
            "unassigned": result.get("unassigned", []),
            "analysis":   analysis,
            "statistics": statistics,
            "_metadata": {
                "api_key":            api_key_info["name"],
                "engine":             "valhalla",
                "control_level":      "PREMIUM",
                "two_pass":           num_jobs >= 10,
                "processing_time_ms": processing_time,
            },
        }

    except Exception as e:
        logger.error(f"/valhalla/optimize/premium failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─── helpers ──────────────────────────────────────────────────────────────────

async def _retry_valhalla(c, vrp_input: dict, initial_result: dict) -> dict:
    """제약조건 완화 후 Valhalla로 재시도"""
    try:
        tuned = c.controller.constraint_tuner.auto_tune_for_unassigned(
            vrp_input, initial_result.get("unassigned", [])
        )
        retry = await c.valhalla_executor.execute(tuned, geometry=True)
        if len(retry.get("unassigned", [])) < len(initial_result.get("unassigned", [])):
            return retry
    except Exception as e:
        logger.warning(f"Valhalla retry failed: {e}")
    return initial_result
