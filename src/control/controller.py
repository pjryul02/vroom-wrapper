#!/usr/bin/env python3
"""
OptimizationController - v3.0 정반합

v3.0 변경사항:
- VROOMExecutor 직접 호출 (vroom-express 제거)
- TwoPassOptimizer 2단계 최적화
- UnreachableFilter 도달 불가능 필터링
- 기존 HTTP 호출 폴백 유지
"""

from typing import Dict, List, Any, Optional
import httpx
import logging

from .vroom_config import VROOMConfigManager, ControlLevel
from .constraint_tuner import ConstraintTuner
from .multi_scenario import MultiScenarioEngine, ScenarioGenerator

from ..optimization.vroom_executor import VROOMExecutor
from ..optimization.two_pass import TwoPassOptimizer
from ..preprocessing.unreachable_filter import UnreachableFilter

from .. import config

logger = logging.getLogger(__name__)


class OptimizationController:
    """
    최적화 제어 계층 v3.0

    Roouty Engine 패턴 통합:
    - VROOM 바이너리 직접 호출 (stdin/stdout)
    - 2-Pass 최적화 (초기 배정 + 경로별 최적화)
    - 도달 불가능 작업 사전 필터링
    """

    def __init__(
        self,
        vroom_url: str = "http://localhost:3000",
        enable_multi_scenario: bool = False,
        # v3.0 새 옵션
        use_direct_call: Optional[bool] = None,
        vroom_path: Optional[str] = None,
        enable_two_pass: Optional[bool] = None,
        enable_unreachable_filter: Optional[bool] = None,
    ):
        # 설정 (인자 > 환경변수 > 기본값)
        self.use_direct_call = use_direct_call if use_direct_call is not None else config.USE_DIRECT_CALL
        self.vroom_url = vroom_url
        self.enable_multi_scenario = enable_multi_scenario

        # v3.0: VROOMExecutor (직접 호출)
        self.executor = None
        if self.use_direct_call:
            vroom_binary = vroom_path or config.VROOM_BINARY_PATH
            try:
                self.executor = VROOMExecutor(
                    vroom_path=vroom_binary,
                    router=config.VROOM_ROUTER,
                    router_host=config.OSRM_URL.replace("http://", "").split(":")[0],
                    router_port=int(config.OSRM_URL.split(":")[-1]),
                    default_threads=config.VROOM_THREADS,
                    default_exploration=config.VROOM_EXPLORATION,
                    timeout=config.VROOM_TIMEOUT,
                )
                logger.info(f"VROOMExecutor 초기화 완료 (binary: {vroom_binary})")
            except Exception as e:
                logger.warning(f"VROOMExecutor 초기화 실패: {e} - HTTP 폴백 사용")
                self.use_direct_call = False

        # v3.0: TwoPassOptimizer
        _enable_two_pass = enable_two_pass if enable_two_pass is not None else config.TWO_PASS_ENABLED
        self.two_pass_optimizer = None
        if _enable_two_pass and self.executor:
            self.two_pass_optimizer = TwoPassOptimizer(
                executor=self.executor,
                max_workers=config.TWO_PASS_MAX_WORKERS,
                initial_threads=config.TWO_PASS_INITIAL_THREADS,
                route_threads=config.TWO_PASS_ROUTE_THREADS,
            )
            logger.info(
                f"TwoPassOptimizer 초기화 완료 "
                f"(workers={config.TWO_PASS_MAX_WORKERS})"
            )

        # v3.0: UnreachableFilter
        _enable_filter = enable_unreachable_filter if enable_unreachable_filter is not None else config.UNREACHABLE_FILTER_ENABLED
        self.unreachable_filter = None
        if _enable_filter:
            self.unreachable_filter = UnreachableFilter(
                threshold=config.UNREACHABLE_THRESHOLD
            )

        # 기존 컴포넌트
        self.config_manager = VROOMConfigManager()
        self.constraint_tuner = ConstraintTuner()
        self.multi_scenario_engine = MultiScenarioEngine(
            vroom_optimizer_fn=self._call_vroom
        )

    async def optimize(
        self,
        vrp_input: Dict[str, Any],
        control_level: ControlLevel = ControlLevel.STANDARD,
        custom_config: Optional[Dict[str, Any]] = None,
        enable_auto_retry: bool = True
    ) -> Dict[str, Any]:
        """
        VRP 최적화 실행

        v3.0 파이프라인:
        1. VROOM 설정 생성
        2. 도달 불가능 필터링 (v3.0)
        3. 2-Pass / 다중 시나리오 / 단일 최적화
        4. 미배정 자동 재시도
        """
        # 1. VROOM 설정 생성
        vroom_config = self.config_manager.get_config(control_level, custom_config)

        num_jobs = len(vrp_input.get('jobs', [])) + len(vrp_input.get('shipments', []))
        num_vehicles = len(vrp_input.get('vehicles', []))

        vroom_config = self.config_manager.tune_for_problem_size(
            vroom_config, num_jobs, num_vehicles
        )

        # VIP/긴급 작업 탐지
        has_vip, has_urgent = self._detect_priority_jobs(vrp_input)
        if has_vip or has_urgent:
            vroom_config = self.config_manager.get_config_for_priority_jobs(
                vroom_config, has_vip, has_urgent
            )

        # 2. 도달 불가능 필터링 (v3.0 - Roouty 패턴)
        unreachable_jobs = []
        if self.unreachable_filter and vrp_input.get("matrices"):
            vrp_input, unreachable_jobs = self.unreachable_filter.filter(vrp_input)

            if not vrp_input.get("jobs") and not vrp_input.get("shipments"):
                logger.warning("모든 작업 도달 불가능 - VROOM 호출 스킵")
                return {
                    "code": 0,
                    "summary": {"cost": 0, "unassigned": len(unreachable_jobs)},
                    "routes": [],
                    "unassigned": unreachable_jobs,
                }

        # 3. 최적화 실행
        if self.enable_multi_scenario or control_level == ControlLevel.PREMIUM:
            # 다중 시나리오 (기존)
            result = await self._optimize_multi_scenario(vrp_input, vroom_config)

        elif self.two_pass_optimizer and num_jobs >= 10:
            # 2-Pass 최적화 (v3.0 - 10개 이상 작업일 때)
            logger.info(f"[2-PASS] 2단계 최적화 실행 (jobs={num_jobs})")
            result = await self.two_pass_optimizer.optimize(vrp_input)

        else:
            # 단일 최적화
            result = await self._call_vroom(vrp_input, vroom_config)

        # 도달 불가능 작업을 unassigned에 추가
        if unreachable_jobs:
            existing = result.get("unassigned", [])
            result["unassigned"] = existing + unreachable_jobs
            result.setdefault("summary", {})["unassigned"] = len(result["unassigned"])

        # 4. 미배정 자동 재시도
        if enable_auto_retry and result.get('unassigned'):
            # unreachable은 재시도해도 의미 없으므로 제외
            retryable = [
                u for u in result.get("unassigned", [])
                if u.get("reason") != "unreachable"
            ]
            if retryable:
                result = await self._retry_with_relaxation(vrp_input, vroom_config, result)

        return result

    async def _call_vroom(
        self,
        vrp_input: Dict[str, Any],
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        VROOM 호출 (v3.0 - 직접 호출 우선, HTTP 폴백)
        """
        exploration = None
        if config and 'exploration_level' in config:
            exploration = config['exploration_level']

        # v3.0: 직접 호출 모드
        # Always enable geometry for OSRM road-following routes
        if self.use_direct_call and self.executor:
            return await self.executor.execute(
                vrp_input,
                exploration=exploration,
                geometry=True,
            )

        # 폴백: HTTP 호출 (기존 vroom-express)
        return await self._call_vroom_http(vrp_input, config)

    async def _call_vroom_http(
        self,
        vrp_input: Dict[str, Any],
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """기존 HTTP 호출 (vroom-express 폴백)"""
        vroom_payload = vrp_input.copy()

        if config:
            if 'options' not in vroom_payload:
                vroom_payload['options'] = {}
            if 'exploration_level' in config:
                vroom_payload['options']['g'] = config['exploration_level']

        try:
            async with httpx.AsyncClient(
                timeout=config.get('timeout', 30000) / 1000 if config else 30.0
            ) as client:
                response = await client.post(
                    f"{self.vroom_url}",
                    json=vroom_payload
                )
                response.raise_for_status()
                return response.json()

        except httpx.RequestError as e:
            logger.error(f"VROOM HTTP request failed: {e}")
            raise
        except httpx.HTTPStatusError as e:
            logger.error(f"VROOM HTTP error: {e.response.status_code}")
            raise

    async def _optimize_multi_scenario(
        self,
        vrp_input: Dict[str, Any],
        base_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """다중 시나리오 최적화"""
        logger.info("Multi-scenario optimization enabled")

        scenarios = ScenarioGenerator.generate_control_level_scenarios(
            vrp_input, self.config_manager
        )

        results = await self.multi_scenario_engine.run_scenarios(scenarios)

        if not results:
            logger.error("All scenarios failed, falling back to single optimization")
            return await self._call_vroom(vrp_input, base_config)

        best_result = self.multi_scenario_engine.select_best_result(
            results, criteria='score'
        )

        comparison = self.multi_scenario_engine.compare_results(results)

        final_result = best_result.vroom_result.copy()
        final_result['multi_scenario_metadata'] = {
            'selected_scenario': best_result.scenario_name,
            'total_scenarios': len(results),
            'comparison': comparison
        }

        return final_result

    async def _retry_with_relaxation(
        self,
        vrp_input: Dict[str, Any],
        config: Dict[str, Any],
        initial_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """제약조건 완화 후 재시도"""
        unassigned = initial_result.get('unassigned', [])

        if not unassigned:
            return initial_result

        logger.info(f"Found {len(unassigned)} unassigned jobs, attempting relaxation...")

        suggestions = self.constraint_tuner.suggest_constraint_adjustments(
            vrp_input, unassigned
        )

        tuned_input = self.constraint_tuner.auto_tune_for_unassigned(
            vrp_input, unassigned
        )

        retry_result = await self._call_vroom(tuned_input, config)

        retry_unassigned = len(retry_result.get('unassigned', []))
        initial_unassigned = len(unassigned)

        if retry_unassigned < initial_unassigned:
            improvement = initial_unassigned - retry_unassigned
            logger.info(
                f"Relaxation successful: {initial_unassigned} → {retry_unassigned} (-{improvement})"
            )
            retry_result['relaxation_metadata'] = {
                'applied': True,
                'initial_unassigned': initial_unassigned,
                'final_unassigned': retry_unassigned,
                'improvement': improvement,
                'suggestions': suggestions
            }
            return retry_result

        logger.info("Relaxation did not improve result")
        return initial_result

    def _detect_priority_jobs(self, vrp_input: Dict[str, Any]) -> tuple:
        """VIP/긴급 작업 탐지"""
        VIP_SKILL = 10000
        URGENT_SKILL = 10001
        has_vip = False
        has_urgent = False

        for job in vrp_input.get('jobs', []):
            skills = job.get('skills', [])
            if VIP_SKILL in skills:
                has_vip = True
            if URGENT_SKILL in skills:
                has_urgent = True

        return has_vip, has_urgent
