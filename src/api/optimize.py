"""POST /optimize, /optimize/basic, /optimize/premium"""

import time
import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Header

from ..api_models import OptimizeRequest
from ..postprocessing import ConstraintChecker
from ..control import OptimizationController, ControlLevel
from ..core.auth import verify_api_key, check_rate_limit
from ..core.dependencies import get_components
from .. import config

logger = logging.getLogger(__name__)
router = APIRouter()


def _analyze_unassigned(vrp_input: dict, result: dict):
    """미배정 사유 분석 공통 로직"""
    if not result.get('unassigned'):
        return
    try:
        checker = ConstraintChecker(vrp_input)
        reasons_map = checker.analyze_unassigned(result['unassigned'])
        for unassigned in result['unassigned']:
            job_id = unassigned.get('id')
            if job_id in reasons_map:
                unassigned['reasons'] = reasons_map[job_id]
    except Exception:
        pass


@router.post(
    "/optimize",
    tags=["최적화"],
    summary="STANDARD 최적화 (전체 파이프라인)",
    description="""
전체 파이프라인을 실행하는 표준 최적화.

**처리 순서**: 전처리 → 도달불가 필터 → 2-Pass 최적화 → 자동 재시도 → 분석 → 통계 → 캐싱

### 응답 추가 필드
- `analysis`: 품질 점수, 개선 제안, 차량 활용률
- `statistics`: 거리/시간 통계
- `_metadata`: 처리 시간, 캐시 여부

### 인증
`X-API-Key` 헤더 필수. 데모 키: `demo-key-12345`
""",
    responses={
        200: {"description": "최적화 성공 (routes, summary, analysis, statistics 포함)"},
        401: {"description": "API Key 누락 또는 유효하지 않음"},
        429: {"description": "요청률 제한 초과"},
        500: {"description": "VROOM 실행 오류 또는 내부 오류"},
    },
)
async def optimize_standard(
    request_body: OptimizeRequest,
    x_api_key: Optional[str] = Header(None, description="API Key (필수). 데모: demo-key-12345")
) -> Dict[str, Any]:
    api_key_info = verify_api_key(x_api_key)
    check_rate_limit(x_api_key)

    c = get_components()
    start_time = time.time()

    try:
        use_cache = request_body.use_cache if request_body.use_cache is not None else True
        business_rules = request_body.business_rules.model_dump(exclude_none=True) if request_body.business_rules else None
        vrp_data = request_body.model_dump(exclude_none=True)
        vrp_data.pop('use_cache', None)
        vrp_data.pop('business_rules', None)

        # 캐시 확인
        if use_cache:
            cached = c.cache_manager.get(vrp_data)
            if cached:
                logger.info(f"Cache hit for {api_key_info['name']}")
                cached['_metadata'] = {
                    'from_cache': True,
                    'cached_at': cached.get('_metadata', {}).get('timestamp', 'unknown')
                }
                return cached

        # Phase 1: 전처리
        vrp_input = await c.preprocessor.process(vrp_data, business_rules)

        # Phase 2: 최적화
        vroom_result = await c.controller.optimize(
            vrp_input,
            control_level=ControlLevel.STANDARD,
            enable_auto_retry=True
        )

        # 미배정 사유 분석
        _analyze_unassigned(vrp_input, vroom_result)

        # Phase 3: 분석 및 통계
        analysis = c.analyzer.analyze(vrp_input, vroom_result)
        statistics = c.stats_generator.generate(vrp_input, vroom_result)

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
                'timestamp': time.time(),
                **vroom_result.get('_execution', {}),
            }
        }

        if 'relaxation_metadata' in vroom_result:
            response['relaxation_metadata'] = vroom_result['relaxation_metadata']

        if use_cache:
            c.cache_manager.set(vrp_data, response, ttl=3600)

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


@router.post(
    "/optimize/basic",
    tags=["최적화"],
    summary="BASIC 최적화 (빠른 결과)",
    description="""
분석(analysis)과 통계(statistics)를 생략한 경량 최적화. 자동 재시도도 하지 않는다.
캐싱 없이 빠른 결과가 필요할 때 사용.

### 인증
`X-API-Key` 헤더 필수.
""",
)
async def optimize_basic(
    request_body: OptimizeRequest,
    x_api_key: Optional[str] = Header(None, description="API Key (필수)")
) -> Dict[str, Any]:
    api_key_info = verify_api_key(x_api_key)
    check_rate_limit(x_api_key)

    c = get_components()

    try:
        vrp_data = request_body.model_dump(exclude_none=True)
        vrp_data.pop('use_cache', None)
        vrp_data.pop('business_rules', None)
        vrp_input = await c.preprocessor.process(vrp_data)
        result = await c.controller.optimize(
            vrp_input,
            control_level=ControlLevel.BASIC,
            enable_auto_retry=False
        )

        _analyze_unassigned(vrp_input, result)

        return {
            'wrapper_version': '3.0.0',
            'routes': result.get('routes', []),
            'summary': result.get('summary', {}),
            'unassigned': result.get('unassigned', []),
            '_metadata': {
                'api_key': api_key_info['name'],
                'control_level': 'BASIC',
                'engine': 'direct' if config.USE_DIRECT_CALL else 'http',
                **result.get('_execution', {}),
            }
        }
    except Exception as e:
        logger.error(f"BASIC optimization failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/optimize/premium",
    tags=["최적화"],
    summary="PREMIUM 최적화 (멀티 시나리오 + 2-Pass)",
    description="""
멀티 시나리오 비교와 2-Pass 최적화를 포함한 최고 품질 최적화.

### 처리
1. 여러 시나리오(탐색 강도, 제약 조합)를 병렬 실행
2. 각 시나리오에서 2-Pass 최적화 (Pass1: 배정, Pass2: 경로)
3. 최적 시나리오 자동 선택

### 추가 응답 필드
- `multi_scenario_metadata`: 시나리오 비교 결과

### 인증
`X-API-Key` 헤더 필수. Premium 권한 필요. 요청률 50/시간.
""",
    responses={
        200: {"description": "최적화 성공 (멀티 시나리오 메타데이터 포함)"},
        401: {"description": "API Key 누락 또는 유효하지 않음"},
        403: {"description": "Premium 권한 없음"},
        429: {"description": "요청률 제한 초과 (50/시간)"},
    },
)
async def optimize_premium(
    request_body: OptimizeRequest,
    x_api_key: Optional[str] = Header(None, description="API Key (필수, Premium 권한)")
) -> Dict[str, Any]:
    api_key_info = verify_api_key(x_api_key)

    if 'premium' not in api_key_info.get('features', []):
        raise HTTPException(
            status_code=403,
            detail="Premium feature not available for this API key"
        )

    check_rate_limit(x_api_key, limit=50)

    c = get_components()
    start_time = time.time()

    try:
        vrp_data = request_body.model_dump(exclude_none=True)
        vrp_data.pop('use_cache', None)
        vrp_data.pop('business_rules', None)
        vrp_input = await c.preprocessor.process(vrp_data)

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

        _analyze_unassigned(vrp_input, result)

        analysis = c.analyzer.analyze(vrp_input, result)
        statistics = c.stats_generator.generate(vrp_input, result)

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
                'processing_time_ms': processing_time,
                **result.get('_execution', {}),
            }
        }
    except Exception as e:
        logger.error(f"PREMIUM optimization failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
