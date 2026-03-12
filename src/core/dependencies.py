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
from ..preprocessing.valhalla_matrix import ValhallaChunkedMatrix
from ..preprocessing.vroom_matrix_preparer import VroomMatrixPreparer
from ..preprocessing.valhalla_eta import ValhallaEtaUpdater
from ..control import OptimizationController
from ..optimization.vroom_executor import VROOMExecutor
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
    # Valhalla 컴포넌트 (옵션)
    valhalla_executor: Optional[VROOMExecutor] = None
    valhalla_matrix: Optional[ValhallaChunkedMatrix] = None
    valhalla_preparer: Optional[VroomMatrixPreparer] = None
    valhalla_eta_updater: Optional[ValhallaEtaUpdater] = None  # Pass 3: ETA 업데이터


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

    # ── Valhalla 컴포넌트 (선택적) ───────────────────────────────────────────
    valhalla_executor = None
    valhalla_matrix   = None
    valhalla_preparer = None

    if config.VALHALLA_URL:
        try:
            vh = config.VALHALLA_URL.replace("http://", "").replace("https://", "")
            vh_host = vh.split(":")[0]
            vh_port = int(vh.split(":")[-1]) if ":" in vh else 8002

            valhalla_executor = VROOMExecutor(
                vroom_path=config.VROOM_BINARY_PATH,
                router="valhalla",
                router_host=vh_host,
                router_port=vh_port,
                default_threads=config.VROOM_THREADS,
                default_exploration=config.VROOM_EXPLORATION,
                timeout=config.VROOM_TIMEOUT,
            )

            valhalla_matrix = ValhallaChunkedMatrix(
                valhalla_url=config.VALHALLA_URL,
                chunk_size=config.VALHALLA_CHUNK_SIZE,
                max_workers=config.VALHALLA_MAX_WORKERS,
            )

            valhalla_preparer = VroomMatrixPreparer(
                osrm_matrix=valhalla_matrix,  # 같은 인터페이스 (build_matrix 메서드)
                profile="auto",  # Valhalla: "auto" costing = VROOM의 car에 대응
            )

            # Pass 3: Valhalla ETA 업데이터 (HGLIS dispatch 전용)
            # 현재: 틀만 잡힌 상태 (pass-through), TODO: /route API 구현 후 활성화
            valhalla_eta_updater = ValhallaEtaUpdater(
                valhalla_url=config.VALHALLA_URL,
                costing="auto",   # 소형화물차 기본값
                enabled=False,    # TODO: 구현 완료 후 True로 변경
            )

            logger.info(
                f"Valhalla 컴포넌트 초기화 완료 "
                f"(executor: {vh_host}:{vh_port}, "
                f"matrix chunk_size={config.VALHALLA_CHUNK_SIZE}, "
                f"eta_updater: pass-through)"
            )
        except Exception as e:
            logger.warning(f"Valhalla 컴포넌트 초기화 실패 (비활성): {e}")
            valhalla_eta_updater = None

    _components = Components(
        preprocessor=preprocessor,
        controller=controller,
        analyzer=analyzer,
        stats_generator=stats_generator,
        cache_manager=cache_manager,
        matrix_builder=matrix_builder,
        map_matcher=map_matcher,
        valhalla_executor=valhalla_executor,
        valhalla_matrix=valhalla_matrix,
        valhalla_preparer=valhalla_preparer,
        valhalla_eta_updater=valhalla_eta_updater,
    )

    logger.info("All components initialized")
    return _components


def get_components() -> Components:
    """현재 컴포넌트 인스턴스 반환"""
    if _components is None:
        return init_components()
    return _components
