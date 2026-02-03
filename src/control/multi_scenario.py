#!/usr/bin/env python3
"""
MultiScenarioEngine - 다중 시나리오 최적화

Phase 2.2: 여러 설정으로 동시 최적화 후 최적 결과 선택
"""

from typing import Dict, List, Any, Optional, Callable, Tuple
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)


class ScenarioResult:
    """시나리오 실행 결과"""

    def __init__(
        self,
        scenario_name: str,
        vrp_input: Dict[str, Any],
        vroom_result: Dict[str, Any],
        config: Dict[str, Any]
    ):
        self.scenario_name = scenario_name
        self.vrp_input = vrp_input
        self.vroom_result = vroom_result
        self.config = config

        # 결과 메트릭 계산
        self.num_assigned = len(self._get_assigned_jobs())
        self.num_unassigned = len(vroom_result.get('unassigned', []))
        self.total_cost = vroom_result.get('summary', {}).get('cost', float('inf'))
        self.total_duration = vroom_result.get('summary', {}).get('duration', 0)
        self.total_distance = vroom_result.get('summary', {}).get('distance', 0)

    def _get_assigned_jobs(self) -> List[int]:
        """배정된 작업 ID 리스트"""
        assigned = []
        for route in self.vroom_result.get('routes', []):
            for step in route.get('steps', []):
                if step.get('type') == 'job':
                    assigned.append(step.get('job'))
        return assigned

    def get_score(self) -> float:
        """
        시나리오 점수 계산

        - 배정된 작업 수: 높을수록 좋음
        - 총 비용: 낮을수록 좋음
        - 미배정 작업 수: 낮을수록 좋음

        Returns:
            점수 (높을수록 좋음)
        """
        # 배정률 (0-100)
        assignment_rate = self.num_assigned / (self.num_assigned + self.num_unassigned) * 100 if (self.num_assigned + self.num_unassigned) > 0 else 0

        # 비용 페널티 (정규화)
        cost_penalty = self.total_cost / 10000  # 스케일 조정

        # 미배정 페널티
        unassigned_penalty = self.num_unassigned * 50

        # 최종 점수
        score = assignment_rate - cost_penalty - unassigned_penalty

        return score

    def __repr__(self):
        return (
            f"ScenarioResult({self.scenario_name}, "
            f"assigned={self.num_assigned}, "
            f"unassigned={self.num_unassigned}, "
            f"cost={self.total_cost}, "
            f"score={self.get_score():.2f})"
        )


class MultiScenarioEngine:
    """
    다중 시나리오 최적화 엔진

    여러 설정/전략으로 동시에 최적화 실행 후 최적 결과 선택
    """

    def __init__(self, vroom_optimizer_fn: Callable):
        """
        Args:
            vroom_optimizer_fn: VROOM 최적화 함수
                async def optimize(vrp_input, config) -> vroom_result
        """
        self.vroom_optimizer = vroom_optimizer_fn

    async def run_scenarios(
        self,
        scenarios: List[Tuple[str, Dict[str, Any], Dict[str, Any]]]
    ) -> List[ScenarioResult]:
        """
        여러 시나리오 병렬 실행

        Args:
            scenarios: [(시나리오 이름, VRP 입력, VROOM 설정)] 리스트

        Returns:
            ScenarioResult 리스트
        """
        tasks = []

        for scenario_name, vrp_input, config in scenarios:
            task = self._run_single_scenario(scenario_name, vrp_input, config)
            tasks.append(task)

        logger.info(f"Running {len(scenarios)} scenarios in parallel...")

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 성공한 결과만 필터링
        successful_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Scenario {scenarios[i][0]} failed: {result}")
            else:
                successful_results.append(result)

        logger.info(f"Completed {len(successful_results)}/{len(scenarios)} scenarios")

        return successful_results

    async def _run_single_scenario(
        self,
        scenario_name: str,
        vrp_input: Dict[str, Any],
        config: Dict[str, Any]
    ) -> ScenarioResult:
        """단일 시나리오 실행"""
        logger.debug(f"Running scenario: {scenario_name}")

        try:
            vroom_result = await self.vroom_optimizer(vrp_input, config)

            result = ScenarioResult(
                scenario_name=scenario_name,
                vrp_input=vrp_input,
                vroom_result=vroom_result,
                config=config
            )

            logger.debug(f"Scenario {scenario_name} completed: {result}")

            return result

        except Exception as e:
            logger.error(f"Scenario {scenario_name} failed: {e}")
            raise

    def select_best_result(
        self,
        results: List[ScenarioResult],
        criteria: str = 'score'
    ) -> Optional[ScenarioResult]:
        """
        최적 결과 선택

        Args:
            results: 시나리오 결과 리스트
            criteria: 선택 기준
                - 'score': 종합 점수 (기본)
                - 'assigned': 배정된 작업 수
                - 'cost': 총 비용 (낮을수록 좋음)
                - 'unassigned': 미배정 작업 수 (낮을수록 좋음)

        Returns:
            최적 ScenarioResult 또는 None
        """
        if not results:
            logger.warning("No results to select from")
            return None

        if criteria == 'score':
            best = max(results, key=lambda r: r.get_score())
        elif criteria == 'assigned':
            best = max(results, key=lambda r: r.num_assigned)
        elif criteria == 'cost':
            best = min(results, key=lambda r: r.total_cost)
        elif criteria == 'unassigned':
            best = min(results, key=lambda r: r.num_unassigned)
        else:
            logger.warning(f"Unknown criteria '{criteria}', using 'score'")
            best = max(results, key=lambda r: r.get_score())

        logger.info(f"Selected best result: {best.scenario_name} (criteria: {criteria})")

        return best

    def compare_results(
        self,
        results: List[ScenarioResult]
    ) -> Dict[str, Any]:
        """
        시나리오 결과 비교

        Args:
            results: 시나리오 결과 리스트

        Returns:
            비교 리포트
        """
        if not results:
            return {'error': 'No results to compare'}

        comparison = {
            'total_scenarios': len(results),
            'scenarios': []
        }

        for result in results:
            comparison['scenarios'].append({
                'name': result.scenario_name,
                'assigned': result.num_assigned,
                'unassigned': result.num_unassigned,
                'cost': result.total_cost,
                'duration': result.total_duration,
                'distance': result.total_distance,
                'score': result.get_score()
            })

        # 정렬 (점수 높은 순)
        comparison['scenarios'].sort(key=lambda s: s['score'], reverse=True)

        # 최고/최저 메트릭
        comparison['best_assignment'] = max(
            comparison['scenarios'],
            key=lambda s: s['assigned']
        )['name']

        comparison['lowest_cost'] = min(
            comparison['scenarios'],
            key=lambda s: s['cost']
        )['name']

        comparison['fewest_unassigned'] = min(
            comparison['scenarios'],
            key=lambda s: s['unassigned']
        )['name']

        return comparison


class ScenarioGenerator:
    """시나리오 생성 헬퍼"""

    @staticmethod
    def generate_control_level_scenarios(
        vrp_input: Dict[str, Any],
        config_manager
    ) -> List[Tuple[str, Dict[str, Any], Dict[str, Any]]]:
        """
        제어 레벨별 시나리오 생성

        Args:
            vrp_input: VRP 입력
            config_manager: VROOMConfigManager 인스턴스

        Returns:
            [(시나리오 이름, VRP 입력, VROOM 설정)] 리스트
        """
        from .vroom_config import ControlLevel

        scenarios = []

        for level in [ControlLevel.BASIC, ControlLevel.STANDARD, ControlLevel.PREMIUM]:
            config = config_manager.get_config(level)
            scenarios.append((
                f"Level: {level.value}",
                vrp_input,
                config
            ))

        return scenarios

    @staticmethod
    def generate_relaxation_scenarios(
        vrp_input: Dict[str, Any],
        base_config: Dict[str, Any],
        constraint_tuner
    ) -> List[Tuple[str, Dict[str, Any], Dict[str, Any]]]:
        """
        제약조건 완화 시나리오 생성

        Args:
            vrp_input: VRP 입력
            base_config: 기본 VROOM 설정
            constraint_tuner: ConstraintTuner 인스턴스

        Returns:
            [(시나리오 이름, VRP 입력, VROOM 설정)] 리스트
        """
        scenarios = []

        # 원본
        scenarios.append(("Original", vrp_input, base_config))

        # 완화 시나리오
        relaxation_scenarios = constraint_tuner.generate_relaxation_scenarios(
            vrp_input,
            max_scenarios=3
        )

        for name, relaxed_input in relaxation_scenarios:
            scenarios.append((name, relaxed_input, base_config))

        return scenarios
