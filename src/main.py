#!/usr/bin/env python3
"""
VROOM Wrapper v2.0 - 완전판

Phase 5 포함:
- Rate Limiting
- API Key 인증
- Redis 캐싱
- 통계 생성
- 전체 파이프라인 통합
"""

from fastapi import FastAPI, HTTPException, Header, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any, Optional
import logging
import time
import os

# Phase 1: Pre-processing
from preprocessing import PreProcessor

# Phase 2: Control
from control import OptimizationController, ControlLevel

# Phase 3: Post-processing
from postprocessing import ResultAnalyzer, StatisticsGenerator

# Phase 4: Extensions
from extensions import CacheManager

# v1.0 통합
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
    title="VROOM Wrapper v2.0 - Complete Edition",
    version="2.0.0",
    description="Complete VRP optimization platform with caching, rate limiting, and authentication"
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
stats_generator = StatisticsGenerator()

# Redis 캐싱 (환경변수에서 URL 가져오기, 없으면 메모리 캐시)
redis_url = os.getenv('REDIS_URL')  # 예: redis://localhost:6379
cache_manager = CacheManager(redis_url=redis_url)

# API Key 관리
API_KEYS = {
    "demo-key-12345": {
        "name": "Demo Client",
        "rate_limit": "100/hour",
        "features": ["basic", "standard", "premium"]
    },
    "test-key-67890": {
        "name": "Test Client",
        "rate_limit": "50/hour",
        "features": ["basic", "standard"]
    }
}


def verify_api_key(x_api_key: Optional[str] = Header(None)) -> Dict:
    """API Key 검증"""
    if not x_api_key:
        raise HTTPException(
            status_code=401,
            detail="API Key required (Header: X-API-Key)"
        )

    if x_api_key not in API_KEYS:
        raise HTTPException(
            status_code=401,
            detail="Invalid API Key"
        )

    return API_KEYS[x_api_key]


# 간단한 Rate Limiting (메모리 기반)
request_counts = {}


def check_rate_limit(api_key: str, limit: int = 100):
    """간단한 Rate Limiting"""
    current_hour = int(time.time() // 3600)
    key = f"{api_key}:{current_hour}"

    if key not in request_counts:
        request_counts[key] = 0

    request_counts[key] += 1

    if request_counts[key] > limit:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded ({limit} requests/hour)"
        )


@app.post("/optimize")
async def optimize_standard(
    request_body: Dict[str, Any],
    x_api_key: Optional[str] = Header(None)
) -> Dict[str, Any]:
    """
    STANDARD 레벨 최적화 (인증 필요)

    Headers:
        X-API-Key: API 키

    Request Body:
        {
            "vehicles": [...],
            "jobs": [...],
            "use_cache": true,  # optional
            "business_rules": {...}  # optional
        }
    """
    # API Key 검증
    api_key_info = verify_api_key(x_api_key)

    # Rate Limiting
    check_rate_limit(x_api_key, limit=100)

    start_time = time.time()

    try:
        # 캐싱 옵션
        use_cache = request_body.pop('use_cache', True)
        business_rules = request_body.pop('business_rules', None)

        # 캐시 확인
        if use_cache:
            cached = cache_manager.get(request_body)
            if cached:
                logger.info(f"✓ Cache hit for {api_key_info['name']}")
                cached['_metadata'] = {
                    'from_cache': True,
                    'cached_at': cached.get('_metadata', {}).get('timestamp', 'unknown')
                }
                return cached

        # Phase 1: 전처리
        vrp_input = preprocessor.process(request_body, business_rules)

        # Phase 2: 최적화
        vroom_result = await controller.optimize(
            vrp_input,
            control_level=ControlLevel.STANDARD,
            enable_auto_retry=True
        )

        # v1.0: 미배정 사유 분석
        if vroom_result.get('unassigned'):
            checker = ConstraintChecker(vrp_input)
            reasons_map = checker.analyze_unassigned(vroom_result['unassigned'])

            for unassigned in vroom_result['unassigned']:
                job_id = unassigned['id']
                if job_id in reasons_map:
                    unassigned['reasons'] = reasons_map[job_id]

        # Phase 3: 분석 및 통계
        analysis = analyzer.analyze(vrp_input, vroom_result)
        statistics = stats_generator.generate(vrp_input, vroom_result)

        # 최종 응답
        response = {
            'wrapper_version': '2.0.0',
            'routes': vroom_result.get('routes', []),
            'summary': vroom_result.get('summary', {}),
            'unassigned': vroom_result.get('unassigned', []),
            'analysis': analysis,
            'statistics': statistics,
            '_metadata': {
                'api_key': api_key_info['name'],
                'control_level': 'STANDARD',
                'processing_time_ms': int((time.time() - start_time) * 1000),
                'from_cache': False,
                'timestamp': time.time()
            }
        }

        # 캐시에 저장
        if use_cache:
            cache_manager.set(request_body, response, ttl=3600)

        logger.info(
            f"✓ Optimization complete for {api_key_info['name']} "
            f"({int((time.time() - start_time) * 1000)}ms)"
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
    request_body: Dict[str, Any],
    x_api_key: Optional[str] = Header(None)
) -> Dict[str, Any]:
    """BASIC 레벨 최적화 (빠른 결과)"""
    api_key_info = verify_api_key(x_api_key)
    check_rate_limit(x_api_key, limit=100)

    try:
        vrp_input = preprocessor.process(request_body)
        result = await controller.optimize(
            vrp_input,
            control_level=ControlLevel.BASIC,
            enable_auto_retry=False
        )

        return {
            'wrapper_version': '2.0.0',
            'routes': result.get('routes', []),
            'summary': result.get('summary', {}),
            '_metadata': {
                'api_key': api_key_info['name'],
                'control_level': 'BASIC'
            }
        }
    except Exception as e:
        logger.error(f"BASIC optimization failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/optimize/premium")
async def optimize_premium(
    request_body: Dict[str, Any],
    x_api_key: Optional[str] = Header(None)
) -> Dict[str, Any]:
    """PREMIUM 레벨 최적화 (다중 시나리오)"""
    api_key_info = verify_api_key(x_api_key)

    # Premium 기능 체크
    if 'premium' not in api_key_info.get('features', []):
        raise HTTPException(
            status_code=403,
            detail="Premium feature not available for this API key"
        )

    check_rate_limit(x_api_key, limit=50)

    try:
        vrp_input = preprocessor.process(request_body)

        # 다중 시나리오 활성화
        premium_controller = OptimizationController(
            vroom_url="http://localhost:3000",
            enable_multi_scenario=True
        )

        result = await premium_controller.optimize(
            vrp_input,
            control_level=ControlLevel.PREMIUM
        )

        analysis = analyzer.analyze(vrp_input, result)
        statistics = stats_generator.generate(vrp_input, result)

        return {
            'wrapper_version': '2.0.0',
            'routes': result.get('routes', []),
            'summary': result.get('summary', {}),
            'unassigned': result.get('unassigned', []),
            'analysis': analysis,
            'statistics': statistics,
            'multi_scenario_metadata': result.get('multi_scenario_metadata'),
            '_metadata': {
                'api_key': api_key_info['name'],
                'control_level': 'PREMIUM'
            }
        }
    except Exception as e:
        logger.error(f"PREMIUM optimization failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/cache/clear")
async def clear_cache(x_api_key: Optional[str] = Header(None)):
    """캐시 전체 삭제 (관리자용)"""
    verify_api_key(x_api_key)

    cache_manager.clear()

    return {"message": "Cache cleared successfully"}


@app.get("/health")
async def health_check():
    """헬스 체크"""
    return {
        "status": "healthy",
        "version": "2.0.0",
        "components": {
            "preprocessor": "ready",
            "controller": "ready",
            "analyzer": "ready",
            "statistics": "ready",
            "cache": "memory" if not cache_manager.redis_client else "redis"
        }
    }


@app.get("/")
async def root():
    """루트 엔드포인트"""
    return {
        "service": "VROOM Wrapper v2.0 - Complete Edition",
        "version": "2.0.0",
        "endpoints": {
            "optimize": "POST /optimize (STANDARD, requires API Key)",
            "optimize_basic": "POST /optimize/basic (BASIC, requires API Key)",
            "optimize_premium": "POST /optimize/premium (PREMIUM, requires API Key)",
            "clear_cache": "DELETE /cache/clear",
            "health": "GET /health"
        },
        "authentication": "Required (Header: X-API-Key)",
        "demo_api_key": "demo-key-12345",
        "features": [
            "✅ API Key authentication",
            "✅ Rate limiting (100/hour)",
            "✅ Redis caching (with fallback)",
            "✅ Input validation & normalization",
            "✅ Business rules (VIP/urgent/region)",
            "✅ Multi-level optimization (BASIC/STANDARD/PREMIUM)",
            "✅ Constraint relaxation & auto-retry",
            "✅ Multi-scenario optimization",
            "✅ Unassigned reason analysis",
            "✅ Quality scoring & suggestions",
            "✅ Detailed statistics"
        ]
    }


if __name__ == "__main__":
    import uvicorn

    logger.info("Starting VROOM Wrapper v2.0 Complete Edition...")

    if redis_url:
        logger.info(f"✓ Redis caching enabled: {redis_url}")
    else:
        logger.info("✓ Memory caching enabled (set REDIS_URL for Redis)")

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
