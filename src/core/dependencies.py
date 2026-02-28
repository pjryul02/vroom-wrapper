"""
공유 컴포넌트 싱글턴 관리

모든 라우터에서 동일한 인스턴스를 사용하도록 한 곳에서 초기화.
"""

import logging
from dataclasses import dataclass
from typing import Optional

from .. import config
from ..preprocessing import PreProcessor
from ..preprocessing.matrix_builder import TrafficProvider
from ..preprocessing.chunked_matrix import OSRMChunkedMatrix
from ..control import OptimizationController
from ..postprocessing import ResultAnalyzer, StatisticsGenerator, ConstraintChecker
from ..extensions import CacheManager
from ..map_matching import OSRMMapMatcher

logger = logging.getLogger(__name__)


@dataclass
class Components:
    """래퍼 전체에서 공유하는 컴포넌트 모음"""
    preprocessor: PreProcessor
    controller: OptimizationController
    analyzer: ResultAnalyzer
    stats_generator: StatisticsGenerator
    cache_manager: CacheManager
    matrix_builder: OSRMChunkedMatrix
    map_matcher: OSRMMapMatcher


_components: Optional[Components] = None


def init_components() -> Components:
    """컴포넌트 초기화 (앱 시작 시 1회 호출)"""
    global _components

    preprocessor = PreProcessor(
        enable_traffic_matrix=config.TRAFFIC_MATRIX_ENABLED,
        traffic_provider=TrafficProvider(config.TRAFFIC_PROVIDER),
        traffic_api_key=config.get_traffic_api_key(),
        osrm_url=config.OSRM_URL,
    )

    controller = OptimizationController(
        vroom_url=config.VROOM_URL,
        use_direct_call=config.USE_DIRECT_CALL,
        vroom_path=config.VROOM_BINARY_PATH,
        enable_two_pass=config.TWO_PASS_ENABLED,
        enable_unreachable_filter=config.UNREACHABLE_FILTER_ENABLED,
    )

    analyzer = ResultAnalyzer()
    stats_generator = StatisticsGenerator()
    cache_manager = CacheManager(redis_url=config.REDIS_URL)

    matrix_builder = OSRMChunkedMatrix(
        osrm_url=config.OSRM_URL,
        chunk_size=config.OSRM_CHUNK_SIZE,
        max_workers=config.OSRM_MAX_WORKERS,
    )

    map_matcher = OSRMMapMatcher(osrm_url=config.OSRM_URL)

    _components = Components(
        preprocessor=preprocessor,
        controller=controller,
        analyzer=analyzer,
        stats_generator=stats_generator,
        cache_manager=cache_manager,
        matrix_builder=matrix_builder,
        map_matcher=map_matcher,
    )

    logger.info("All components initialized")
    return _components


def get_components() -> Components:
    """현재 컴포넌트 인스턴스 반환"""
    if _components is None:
        return init_components()
    return _components
