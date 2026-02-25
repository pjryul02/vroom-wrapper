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

from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any, Optional
import logging
import time
import os

# API Models (Swagger 문서화용 Pydantic 모델)
from .api_models import DistributeRequest, OptimizeRequest, MatrixBuildRequest

# v3.0 설정
from . import config

# Phase 1: Pre-processing
from .preprocessing import PreProcessor

# Phase 2: Control (v3.0 통합)
from .control import OptimizationController, ControlLevel

# Phase 3: Post-processing
from .postprocessing import ResultAnalyzer, StatisticsGenerator, ConstraintChecker

# Phase 4: Extensions
from .extensions import CacheManager

# v3.0: 대규모 매트릭스 청킹
from .preprocessing.chunked_matrix import OSRMChunkedMatrix

# 실시간 교통 매트릭스 (v2.0 통합)
from .preprocessing.matrix_builder import TrafficProvider

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
# 컴포넌트 초기화
# ============================================================
preprocessor = PreProcessor(
    enable_traffic_matrix=config.TRAFFIC_MATRIX_ENABLED,
    traffic_provider=TrafficProvider(config.TRAFFIC_PROVIDER),
    traffic_api_key=config.get_traffic_api_key(),
    osrm_url=config.OSRM_URL,
)

# v3.0: OptimizationController (VROOM 직접 호출 + 2-Pass + 필터링 통합)
controller = OptimizationController(
    vroom_url=config.VROOM_URL,
    use_direct_call=config.USE_DIRECT_CALL,
    vroom_path=config.VROOM_BINARY_PATH,
    enable_two_pass=config.TWO_PASS_ENABLED,
    enable_unreachable_filter=config.UNREACHABLE_FILTER_ENABLED,
)

analyzer = ResultAnalyzer()
stats_generator = StatisticsGenerator()

# Redis 캐싱
cache_manager = CacheManager(redis_url=config.REDIS_URL)

# v3.0: 대규모 매트릭스 빌더
matrix_builder = OSRMChunkedMatrix(
    osrm_url=config.OSRM_URL,
    chunk_size=config.OSRM_CHUNK_SIZE,
    max_workers=config.OSRM_MAX_WORKERS,
)


# ============================================================
# API Key 인증
# ============================================================
def verify_api_key(x_api_key: Optional[str] = Header(None)) -> Dict:
    """API Key 검증"""
    if not x_api_key:
        raise HTTPException(
            status_code=401,
            detail="API Key required (Header: X-API-Key)"
        )

    if x_api_key not in config.API_KEYS:
        raise HTTPException(
            status_code=401,
            detail="Invalid API Key"
        )

    return config.API_KEYS[x_api_key]


# ============================================================
# Rate Limiting
# ============================================================
request_counts: Dict[str, int] = {}


def check_rate_limit(api_key: str, limit: Optional[int] = None):
    """Rate Limiting 확인"""
    if not config.RATE_LIMIT_ENABLED:
        return

    limit = limit or config.RATE_LIMIT_REQUESTS
    window = config.RATE_LIMIT_WINDOW
    current_window = int(time.time() // window)
    key = f"{api_key}:{current_window}"

    if key not in request_counts:
        request_counts[key] = 0

    request_counts[key] += 1

    if request_counts[key] > limit:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded ({limit} requests/{window}s)"
        )


# ============================================================
# Endpoints
# ============================================================

@app.post("/distribute")
async def distribute(request_body: DistributeRequest) -> Dict[str, Any]:
    """
    VROOM 호환 배차 엔드포인트

    VROOM 표준 JSON 포맷으로 입출력. API Key 불필요.
    Route Playground 및 외부 VROOM 호환 도구에서 직접 호출 가능.
    부가 기능: 미배정 작업에 대한 사유 분석(reasons)을 자동 포함.
    """
    start_time = time.time()
    vrp_data = request_body.model_dump(exclude_none=True)

    try:
        # Always enable geometry for OSRM road-following routes
        # Without -g flag, VROOM skips OSRM /route calls (distance=None, routing=0)
        options = vrp_data.get('options', {})
        user_requested_geometry = options.get('g', False)

        # Direct VROOM call (bypass preprocessing for max compatibility)
        if controller.executor:
            result = await controller.executor.execute(
                vrp_data,
                geometry=True,  # Always use OSRM for accurate distance/duration
            )
        else:
            # HTTP fallback
            import httpx
            async with httpx.AsyncClient(timeout=300.0) as client:
                resp = await client.post(
                    config.VROOM_URL,
                    json=vrp_data,
                )
                resp.raise_for_status()
                result = resp.json()

        # Wrapper value-add: unassigned reason analysis
        if result.get('unassigned'):
            try:
                checker = ConstraintChecker(vrp_data)
                reasons_map = checker.analyze_unassigned(result['unassigned'])
                for u in result['unassigned']:
                    job_id = u.get('id')
                    if job_id in reasons_map:
                        u['reasons'] = reasons_map[job_id]
            except Exception:
                pass  # Don't fail on analysis error

        # Strip geometry from response if user didn't request it
        if not user_requested_geometry:
            for route in result.get('routes', []):
                route.pop('geometry', None)

        # Ensure VROOM-compatible code field
        if 'code' not in result:
            result['code'] = 0

        # Add wrapper metadata (extra field - won't break VROOM consumers)
        processing_time = int((time.time() - start_time) * 1000)
        result['_wrapper'] = {
            'version': '3.0.0',
            'engine': 'direct' if controller.executor else 'http',
            'processing_time_ms': processing_time,
        }

        return result

    except Exception as e:
        logger.error(f"/distribute failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/optimize")
async def optimize_standard(
    request_body: OptimizeRequest,
    x_api_key: Optional[str] = Header(None)
) -> Dict[str, Any]:
    """
    STANDARD 최적화

    v3.0 파이프라인:
    1. API Key 인증 + Rate Limit
    2. 캐시 확인
    3. 전처리 (검증, 정규화, 비즈니스 규칙)
    4. 도달 불가능 필터링 (v3.0)
    5. VROOM 직접 호출 최적화 (v3.0)
    6. 미배정 자동 재시도
    7. 결과 분석 + 통계
    8. 캐시 저장
    """
    api_key_info = verify_api_key(x_api_key)
    check_rate_limit(x_api_key)

    start_time = time.time()

    try:
        use_cache = request_body.use_cache if request_body.use_cache is not None else True
        business_rules = request_body.business_rules.model_dump(exclude_none=True) if request_body.business_rules else None
        vrp_data = request_body.model_dump(exclude_none=True)
        vrp_data.pop('use_cache', None)
        vrp_data.pop('business_rules', None)

        # 캐시 확인
        if use_cache:
            cached = cache_manager.get(vrp_data)
            if cached:
                logger.info(f"Cache hit for {api_key_info['name']}")
                cached['_metadata'] = {
                    'from_cache': True,
                    'cached_at': cached.get('_metadata', {}).get('timestamp', 'unknown')
                }
                return cached

        # Phase 1: 전처리
        vrp_input = await preprocessor.process(vrp_data, business_rules)

        # Phase 2: 최적화 (v3.0 - 직접호출 + 필터링 + 2-Pass 통합)
        vroom_result = await controller.optimize(
            vrp_input,
            control_level=ControlLevel.STANDARD,
            enable_auto_retry=True
        )

        # v1.0 통합: 미배정 사유 분석
        if vroom_result.get('unassigned'):
            checker = ConstraintChecker(vrp_input)
            reasons_map = checker.analyze_unassigned(vroom_result['unassigned'])
            for unassigned in vroom_result['unassigned']:
                job_id = unassigned.get('id')
                if job_id in reasons_map:
                    unassigned['reasons'] = reasons_map[job_id]

        # Phase 3: 분석 및 통계
        analysis = analyzer.analyze(vrp_input, vroom_result)
        statistics = stats_generator.generate(vrp_input, vroom_result)

        # 최종 응답
        processing_time = int((time.time() - start_time) * 1000)
        response = {
            'wrapper_version': '3.0.0',
            'routes': vroom_result.get('routes', []),
            'summary': vroom_result.get('summary', {}),
            'unassigned': vroom_result.get('unassigned', []),
            'analysis': analysis,
            'statistics': statistics,
            '_metadata': {
                'api_key': api_key_info['name'],
                'control_level': 'STANDARD',
                'engine': 'direct' if config.USE_DIRECT_CALL else 'http',
                'processing_time_ms': processing_time,
                'from_cache': False,
                'timestamp': time.time()
            }
        }

        # 릴렉세이션 메타데이터 포함
        if 'relaxation_metadata' in vroom_result:
            response['relaxation_metadata'] = vroom_result['relaxation_metadata']

        # 캐시에 저장
        if use_cache:
            cache_manager.set(vrp_data, response, ttl=3600)

        logger.info(
            f"Optimization complete for {api_key_info['name']} "
            f"({processing_time}ms, engine={'direct' if config.USE_DIRECT_CALL else 'http'})"
        )

        return response

    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Optimization failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/optimize/basic")
async def optimize_basic(
    request_body: OptimizeRequest,
    x_api_key: Optional[str] = Header(None)
) -> Dict[str, Any]:
    """BASIC 최적화 (빠른 결과, 분석 생략)"""
    api_key_info = verify_api_key(x_api_key)
    check_rate_limit(x_api_key)

    try:
        vrp_data = request_body.model_dump(exclude_none=True)
        vrp_data.pop('use_cache', None)
        vrp_data.pop('business_rules', None)
        vrp_input = await preprocessor.process(vrp_data)
        result = await controller.optimize(
            vrp_input,
            control_level=ControlLevel.BASIC,
            enable_auto_retry=False
        )

        # v1.0 통합: 미배정 사유 분석 (BASIC에서도 제공)
        if result.get('unassigned'):
            checker = ConstraintChecker(vrp_input)
            reasons_map = checker.analyze_unassigned(result['unassigned'])
            for unassigned in result['unassigned']:
                job_id = unassigned.get('id')
                if job_id in reasons_map:
                    unassigned['reasons'] = reasons_map[job_id]

        return {
            'wrapper_version': '3.0.0',
            'routes': result.get('routes', []),
            'summary': result.get('summary', {}),
            'unassigned': result.get('unassigned', []),
            '_metadata': {
                'api_key': api_key_info['name'],
                'control_level': 'BASIC',
                'engine': 'direct' if config.USE_DIRECT_CALL else 'http',
            }
        }
    except Exception as e:
        logger.error(f"BASIC optimization failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/optimize/premium")
async def optimize_premium(
    request_body: OptimizeRequest,
    x_api_key: Optional[str] = Header(None)
) -> Dict[str, Any]:
    """PREMIUM 최적화 (다중 시나리오 + 2-Pass)"""
    api_key_info = verify_api_key(x_api_key)

    if 'premium' not in api_key_info.get('features', []):
        raise HTTPException(
            status_code=403,
            detail="Premium feature not available for this API key"
        )

    check_rate_limit(x_api_key, limit=50)

    start_time = time.time()

    try:
        vrp_data = request_body.model_dump(exclude_none=True)
        vrp_data.pop('use_cache', None)
        vrp_data.pop('business_rules', None)
        vrp_input = await preprocessor.process(vrp_data)

        # PREMIUM: 다중 시나리오 + 2-Pass 활성화
        premium_controller = OptimizationController(
            vroom_url=config.VROOM_URL,
            enable_multi_scenario=True,
            use_direct_call=config.USE_DIRECT_CALL,
            vroom_path=config.VROOM_BINARY_PATH,
            enable_two_pass=True,
            enable_unreachable_filter=True,
        )

        result = await premium_controller.optimize(
            vrp_input,
            control_level=ControlLevel.PREMIUM
        )

        # v1.0 통합: 미배정 사유 분석
        if result.get('unassigned'):
            checker = ConstraintChecker(vrp_input)
            reasons_map = checker.analyze_unassigned(result['unassigned'])
            for unassigned in result['unassigned']:
                job_id = unassigned.get('id')
                if job_id in reasons_map:
                    unassigned['reasons'] = reasons_map[job_id]

        analysis = analyzer.analyze(vrp_input, result)
        statistics = stats_generator.generate(vrp_input, result)

        processing_time = int((time.time() - start_time) * 1000)

        return {
            'wrapper_version': '3.0.0',
            'routes': result.get('routes', []),
            'summary': result.get('summary', {}),
            'unassigned': result.get('unassigned', []),
            'analysis': analysis,
            'statistics': statistics,
            'multi_scenario_metadata': result.get('multi_scenario_metadata'),
            '_metadata': {
                'api_key': api_key_info['name'],
                'control_level': 'PREMIUM',
                'engine': 'direct' if config.USE_DIRECT_CALL else 'http',
                'two_pass': True,
                'processing_time_ms': processing_time,
            }
        }
    except Exception as e:
        logger.error(f"PREMIUM optimization failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/matrix/build")
async def build_matrix(
    request_body: MatrixBuildRequest,
    x_api_key: Optional[str] = Header(None)
) -> Dict[str, Any]:
    """
    v3.0: 대규모 매트릭스 생성 (OSRM 청킹)

    OSRM 서버에서 거리/시간 매트릭스를 75x75 청크 단위로 병렬 생성.
    250개 이상 좌표에서 유용.
    """
    verify_api_key(x_api_key)
    check_rate_limit(x_api_key)

    locations = request_body.locations
    profile = request_body.profile or "driving"

    if not locations:
        raise HTTPException(status_code=400, detail="locations required")

    try:
        result = await matrix_builder.build_matrix(locations, profile)
        return {
            "durations": result["durations"],
            "distances": result["distances"],
            "size": len(locations),
            "_metadata": {
                "chunk_size": config.OSRM_CHUNK_SIZE,
                "max_workers": config.OSRM_MAX_WORKERS,
            }
        }
    except Exception as e:
        logger.error(f"Matrix build failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/cache/clear")
async def clear_cache(x_api_key: Optional[str] = Header(None)):
    """캐시 전체 삭제"""
    verify_api_key(x_api_key)
    cache_manager.clear()
    return {"message": "Cache cleared successfully"}


@app.get("/health")
async def health_check():
    """헬스 체크 (v3.0 - VROOM 바이너리 상태 포함)"""
    vroom_status = "unknown"

    if controller.executor:
        try:
            healthy = await controller.executor.health_check()
            vroom_status = "healthy" if healthy else "unhealthy"
        except Exception:
            vroom_status = "error"
    else:
        vroom_status = "http_fallback"

    return {
        "status": "healthy",
        "version": "3.0.0",
        "engine": "direct" if config.USE_DIRECT_CALL else "http",
        "components": {
            "preprocessor": "ready",
            "controller": "ready",
            "analyzer": "ready",
            "statistics": "ready",
            "cache": "memory" if not cache_manager.redis_client else "redis",
            "vroom_binary": vroom_status,
            "two_pass": "enabled" if controller.two_pass_optimizer else "disabled",
            "unreachable_filter": "enabled" if controller.unreachable_filter else "disabled",
            "matrix_chunking": "ready",
        }
    }


@app.get("/")
async def root():
    """루트 엔드포인트"""
    return {
        "service": "VROOM Wrapper v3.0 - Synthesis Edition",
        "version": "3.0.0",
        "architecture": "Roouty Engine (Go) + Python Wrapper synthesis",
        "endpoints": {
            "distribute": "POST /distribute (VROOM-compatible, no API Key)",
            "optimize": "POST /optimize (STANDARD, requires API Key)",
            "optimize_basic": "POST /optimize/basic (BASIC, requires API Key)",
            "optimize_premium": "POST /optimize/premium (PREMIUM, requires API Key)",
            "matrix_build": "POST /matrix/build (v3.0 chunked matrix)",
            "clear_cache": "DELETE /cache/clear",
            "health": "GET /health"
        },
        "authentication": "Required (Header: X-API-Key)",
        "demo_api_key": "demo-key-12345",
        "v3_features": [
            "VROOM binary direct call (no vroom-express)",
            "2-Pass optimization (assignment + route optimization)",
            "Unreachable job pre-filtering",
            "OSRM chunked matrix (parallel large-scale)",
        ],
        "v2_features": [
            "API Key authentication",
            "Rate limiting",
            "Redis caching (with fallback)",
            "Input validation & normalization",
            "Business rules (VIP/urgent/region)",
            "Multi-level optimization (BASIC/STANDARD/PREMIUM)",
            "Constraint relaxation & auto-retry",
            "Multi-scenario optimization",
            "Quality scoring & suggestions",
            "Detailed statistics",
        ]
    }


# ============================================================
# Startup / Shutdown
# ============================================================

@app.on_event("startup")
async def startup_event():
    """앱 시작 시 초기화"""
    config.print_config()

    if controller.executor:
        logger.info("VROOM engine: direct binary call")
    else:
        logger.info(f"VROOM engine: HTTP fallback ({config.VROOM_URL})")

    if controller.two_pass_optimizer:
        logger.info("2-Pass optimizer: enabled")

    if controller.unreachable_filter:
        logger.info("Unreachable filter: enabled")

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
