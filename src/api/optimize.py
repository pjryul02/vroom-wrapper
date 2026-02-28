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


@router.post("/optimize")
async def optimize_standard(
    request_body: OptimizeRequest,
    x_api_key: Optional[str] = Header(None)
) -> Dict[str, Any]:
    """STANDARD 최적화"""
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
                'timestamp': time.time()
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


@router.post("/optimize/basic")
async def optimize_basic(
    request_body: OptimizeRequest,
    x_api_key: Optional[str] = Header(None)
) -> Dict[str, Any]:
    """BASIC 최적화 (빠른 결과, 분석 생략)"""
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
            }
        }
    except Exception as e:
        logger.error(f"BASIC optimization failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/optimize/premium")
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
                'two_pass': True,
                'processing_time_ms': processing_time,
            }
        }
    except Exception as e:
        logger.error(f"PREMIUM optimization failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
