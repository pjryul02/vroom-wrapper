#!/usr/bin/env python3
"""
OptimizationController - Phase 2 통합

Phase 2.3: VROOMConfigManager, ConstraintTuner, MultiScenarioEngine 통합
"""

from typing import Dict, List, Any, Optional
import httpx
import logging

from .vroom_config import VROOMConfigManager, ControlLevel
from .constraint_tuner import ConstraintTuner
from .multi_scenario import MultiScenarioEngine, ScenarioGenerator

logger = logging.getLogger(__name__)


class OptimizationController:
    """
    최적화 제어 계층

    VROOM 호출 전/후의 모든 제어 로직 담당
    """

    def __init__(
        self,
        vroom_url: str = "http://localhost:3000",
        enable_multi_scenario: bool = False
    ):
        """
        Args:
            vroom_url: VROOM 서버 URL
            enable_multi_scenario: 다중 시나리오 활성화
        """
        self.vroom_url = vroom_url
        self.enable_multi_scenario = enable_multi_scenario

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

        Args:
            vrp_input: 전처리된 VRP 입력
            control_level: 제어 레벨
            custom_config: 사용자 정의 설정
            enable_auto_retry: 미배정 발생 시 자동 재시도

        Returns:
            VROOM 결과 (또는 최적 시나리오 결과)
        """
        # 1. VROOM 설정 생성
        config = self.config_manager.get_config(control_level, custom_config)

        # 2. 문제 크기에 따라 설정 조정
        num_jobs = len(vrp_input.get('jobs', [])) + len(vrp_input.get('shipments', []))
        num_vehicles = len(vrp_input.get('vehicles', []))

        config = self.config_manager.tune_for_problem_size(
            config,
            num_jobs,
            num_vehicles
        )

        # 3. VIP/긴급 작업 탐지
        has_vip, has_urgent = self._detect_priority_jobs(vrp_input)
        if has_vip or has_urgent:
            config = self.config_manager.get_config_for_priority_jobs(
                config,
                has_vip,
                has_urgent
            )

        # 4. 다중 시나리오 실행 (PREMIUM 레벨 또는 명시적 활성화)
        if self.enable_multi_scenario or control_level == ControlLevel.PREMIUM:
            return await self._optimize_multi_scenario(vrp_input, config)

        # 5. 단일 최적화 실행
        result = await self._call_vroom(vrp_input, config)

        # 6. 미배정 발생 시 자동 재시도
        if enable_auto_retry and result.get('unassigned'):
            result = await self._retry_with_relaxation(vrp_input, config, result)

        return result

    async def _optimize_multi_scenario(
        self,
        vrp_input: Dict[str, Any],
        base_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """다중 시나리오 최적화"""
        logger.info("Multi-scenario optimization enabled")

        # 시나리오 생성
        scenarios = ScenarioGenerator.generate_control_level_scenarios(
            vrp_input,
            self.config_manager
        )

        # 시나리오 실행
        results = await self.multi_scenario_engine.run_scenarios(scenarios)

        if not results:
            logger.error("All scenarios failed, falling back to single optimization")
            return await self._call_vroom(vrp_input, base_config)

        # 최적 결과 선택
        best_result = self.multi_scenario_engine.select_best_result(
            results,
            criteria='score'
        )

        # 비교 리포트 추가
        comparison = self.multi_scenario_engine.compare_results(results)

        # 메타데이터 추가
        final_result = best_result.vroom_result.copy()
        final_result['multi_scenario_metadata'] = {
            'selected_scenario': best_result.scenario_name,
            'total_scenarios': len(results),
            'comparison': comparison
        }

        logger.info(f"Selected scenario: {best_result.scenario_name}")

        return final_result

    async def _retry_with_relaxation(
        self,
        vrp_input: Dict[str, Any],
        config: Dict[str, Any],
        initial_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        제약조건 완화 후 재시도

        Args:
            vrp_input: VRP 입력
            config: VROOM 설정
            initial_result: 초기 결과 (미배정 포함)

        Returns:
            개선된 결과 (또는 초기 결과)
        """
        unassigned = initial_result.get('unassigned', [])

        if not unassigned:
            return initial_result

        logger.info(f"Found {len(unassigned)} unassigned jobs, attempting relaxation...")

        # 제약조건 조정 제안
        suggestions = self.constraint_tuner.suggest_constraint_adjustments(
            vrp_input,
            unassigned
        )

        for suggestion in suggestions:
            logger.info(f"Suggestion: {suggestion}")

        # 자동 튜닝 적용
        tuned_input = self.constraint_tuner.auto_tune_for_unassigned(
            vrp_input,
            unassigned
        )

        # 재시도
        retry_result = await self._call_vroom(tuned_input, config)

        # 개선 확인
        retry_unassigned = len(retry_result.get('unassigned', []))
        initial_unassigned = len(unassigned)

        if retry_unassigned < initial_unassigned:
            improvement = initial_unassigned - retry_unassigned
            logger.info(
                f"Relaxation successful: reduced unassigned from "
                f"{initial_unassigned} to {retry_unassigned} (-{improvement})"
            )

            # 메타데이터 추가
            retry_result['relaxation_metadata'] = {
                'applied': True,
                'initial_unassigned': initial_unassigned,
                'final_unassigned': retry_unassigned,
                'improvement': improvement,
                'suggestions': suggestions
            }

            return retry_result
        else:
            logger.info("Relaxation did not improve result, returning initial result")
            return initial_result

    async def _call_vroom(
        self,
        vrp_input: Dict[str, Any],
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        VROOM API 호출

        Args:
            vrp_input: VRP 입력
            config: VROOM 설정 (옵션)

        Returns:
            VROOM 결과
        """
        # VROOM 입력 구성
        vroom_payload = vrp_input.copy()

        # 옵션 추가
        if config:
            if 'options' not in vroom_payload:
                vroom_payload['options'] = {}

            if 'exploration_level' in config:
                vroom_payload['options']['g'] = config['exploration_level']

        try:
            async with httpx.AsyncClient(timeout=config.get('timeout', 30000) / 1000 if config else 30.0) as client:
                response = await client.post(
                    f"{self.vroom_url}",
                    json=vroom_payload
                )

                response.raise_for_status()
                result = response.json()

                logger.debug(f"VROOM call successful: {result.get('summary', {})}")

                return result

        except httpx.RequestError as e:
            logger.error(f"VROOM request failed: {e}")
            raise
        except httpx.HTTPStatusError as e:
            logger.error(f"VROOM returned error: {e.response.status_code}")
            raise

    def _detect_priority_jobs(
        self,
        vrp_input: Dict[str, Any]
    ) -> tuple:
        """
        VIP/긴급 작업 탐지

        Returns:
            (has_vip, has_urgent)
        """
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
