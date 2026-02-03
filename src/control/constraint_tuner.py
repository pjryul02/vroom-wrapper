#!/usr/bin/env python3
"""
ConstraintTuner - 제약조건 자동 조정

Phase 2.2: 미배정 발생 시 제약조건 완화 및 재시도
"""

from typing import Dict, List, Any, Optional, Tuple
import logging
from copy import deepcopy

logger = logging.getLogger(__name__)


class ConstraintRelaxationStrategy:
    """제약조건 완화 전략"""

    @staticmethod
    def relax_time_windows(
        vrp_input: Dict[str, Any],
        factor: float = 1.2
    ) -> Dict[str, Any]:
        """
        시간창 완화 (factor만큼 확장)

        Args:
            vrp_input: VRP 입력
            factor: 확장 비율 (1.2 = 20% 확장)

        Returns:
            완화된 VRP 입력
        """
        relaxed = deepcopy(vrp_input)

        # 작업 시간창 완화
        for job in relaxed.get('jobs', []):
            if 'time_windows' in job and job['time_windows']:
                new_windows = []
                for tw in job['time_windows']:
                    start, end = tw
                    duration = end - start
                    expansion = int(duration * (factor - 1) / 2)

                    new_start = max(0, start - expansion)
                    new_end = end + expansion

                    new_windows.append([new_start, new_end])

                job['time_windows'] = new_windows

        # 차량 시간창 완화
        for vehicle in relaxed.get('vehicles', []):
            if 'time_window' in vehicle and vehicle['time_window']:
                start, end = vehicle['time_window']
                duration = end - start
                expansion = int(duration * (factor - 1) / 2)

                vehicle['time_window'] = [
                    max(0, start - expansion),
                    end + expansion
                ]

        logger.info(f"Relaxed time windows by factor {factor}")
        return relaxed

    @staticmethod
    def increase_vehicle_capacity(
        vrp_input: Dict[str, Any],
        factor: float = 1.3
    ) -> Dict[str, Any]:
        """
        차량 용량 증가

        Args:
            vrp_input: VRP 입력
            factor: 증가 비율 (1.3 = 30% 증가)

        Returns:
            완화된 VRP 입력
        """
        relaxed = deepcopy(vrp_input)

        for vehicle in relaxed.get('vehicles', []):
            if 'capacity' in vehicle:
                vehicle['capacity'] = [
                    int(cap * factor) for cap in vehicle['capacity']
                ]

        logger.info(f"Increased vehicle capacity by factor {factor}")
        return relaxed

    @staticmethod
    def remove_skills_constraints(
        vrp_input: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        스킬 제약조건 제거

        VIP/긴급/지역 제약을 제거하여 모든 차량이 모든 작업 수행 가능

        Args:
            vrp_input: VRP 입력

        Returns:
            완화된 VRP 입력
        """
        relaxed = deepcopy(vrp_input)

        # 작업의 skills 제거
        for job in relaxed.get('jobs', []):
            if 'skills' in job:
                job['skills'] = []

        # 차량의 skills 제거
        for vehicle in relaxed.get('vehicles', []):
            if 'skills' in vehicle:
                vehicle['skills'] = []

        logger.info("Removed all skills constraints")
        return relaxed

    @staticmethod
    def increase_max_tasks(
        vrp_input: Dict[str, Any],
        increment: int = 5
    ) -> Dict[str, Any]:
        """
        차량 최대 작업 수 증가

        Args:
            vrp_input: VRP 입력
            increment: 증가량

        Returns:
            완화된 VRP 입력
        """
        relaxed = deepcopy(vrp_input)

        for vehicle in relaxed.get('vehicles', []):
            if 'max_tasks' in vehicle and vehicle['max_tasks'] is not None:
                vehicle['max_tasks'] += increment

        logger.info(f"Increased max_tasks by {increment}")
        return relaxed

    @staticmethod
    def reduce_service_time(
        vrp_input: Dict[str, Any],
        factor: float = 0.8
    ) -> Dict[str, Any]:
        """
        서비스 시간 감소 (비현실적이지만 최후의 수단)

        Args:
            vrp_input: VRP 입력
            factor: 감소 비율 (0.8 = 20% 감소)

        Returns:
            완화된 VRP 입력
        """
        relaxed = deepcopy(vrp_input)

        for job in relaxed.get('jobs', []):
            if 'service' in job:
                job['service'] = int(job['service'] * factor)

        logger.warning(f"Reduced service time by factor {factor} (unrealistic)")
        return relaxed


class ConstraintTuner:
    """
    제약조건 자동 조정

    미배정 발생 시 단계적으로 제약조건을 완화하여 재시도
    """

    def __init__(self):
        self.strategy = ConstraintRelaxationStrategy()

        # 완화 단계 정의
        self.relaxation_steps = [
            {
                'name': 'Step 1: Relax time windows (20%)',
                'method': lambda inp: self.strategy.relax_time_windows(inp, 1.2)
            },
            {
                'name': 'Step 2: Increase vehicle capacity (30%)',
                'method': lambda inp: self.strategy.increase_vehicle_capacity(inp, 1.3)
            },
            {
                'name': 'Step 3: Increase max tasks (+5)',
                'method': lambda inp: self.strategy.increase_max_tasks(inp, 5)
            },
            {
                'name': 'Step 4: Relax time windows more (50%)',
                'method': lambda inp: self.strategy.relax_time_windows(inp, 1.5)
            },
            {
                'name': 'Step 5: Remove skills constraints',
                'method': self.strategy.remove_skills_constraints
            },
            {
                'name': 'Step 6: Reduce service time (20%)',
                'method': lambda inp: self.strategy.reduce_service_time(inp, 0.8)
            }
        ]

    def generate_relaxation_scenarios(
        self,
        vrp_input: Dict[str, Any],
        max_scenarios: int = 3
    ) -> List[Tuple[str, Dict[str, Any]]]:
        """
        완화 시나리오 생성

        Args:
            vrp_input: 원본 VRP 입력
            max_scenarios: 최대 시나리오 수

        Returns:
            [(시나리오 이름, VRP 입력)] 리스트
        """
        scenarios = []

        current_input = vrp_input

        for i, step in enumerate(self.relaxation_steps[:max_scenarios]):
            relaxed_input = step['method'](current_input)
            scenarios.append((step['name'], relaxed_input))
            current_input = relaxed_input

        return scenarios

    def apply_progressive_relaxation(
        self,
        vrp_input: Dict[str, Any],
        step_index: int
    ) -> Dict[str, Any]:
        """
        점진적 완화 적용

        Args:
            vrp_input: 원본 VRP 입력
            step_index: 완화 단계 (0부터 시작)

        Returns:
            완화된 VRP 입력
        """
        if step_index < 0 or step_index >= len(self.relaxation_steps):
            logger.warning(f"Invalid step_index {step_index}, using 0")
            step_index = 0

        # 지정된 단계까지 순차적으로 완화 적용
        result = vrp_input
        for i in range(step_index + 1):
            step = self.relaxation_steps[i]
            result = step['method'](result)
            logger.info(f"Applied: {step['name']}")

        return result

    def suggest_constraint_adjustments(
        self,
        vrp_input: Dict[str, Any],
        unassigned_jobs: List[Dict[str, Any]]
    ) -> List[str]:
        """
        미배정 사유를 기반으로 제약조건 조정 제안

        Args:
            vrp_input: VRP 입력
            unassigned_jobs: 미배정 작업 리스트 (사유 포함)

        Returns:
            조정 제안 리스트
        """
        suggestions = []

        # 미배정 사유 분석
        reasons = [job.get('reason', '') for job in unassigned_jobs]

        time_window_issues = sum(1 for r in reasons if 'time' in r.lower())
        capacity_issues = sum(1 for r in reasons if 'capacity' in r.lower())
        skills_issues = sum(1 for r in reasons if 'skill' in r.lower())
        max_tasks_issues = sum(1 for r in reasons if 'max_tasks' in r.lower())

        # 제안 생성
        if time_window_issues > len(unassigned_jobs) * 0.3:
            suggestions.append(
                f"시간창 완화 권장 ({time_window_issues}개 작업이 시간창 문제)"
            )

        if capacity_issues > len(unassigned_jobs) * 0.3:
            suggestions.append(
                f"차량 용량 증가 권장 ({capacity_issues}개 작업이 용량 문제)"
            )

        if skills_issues > len(unassigned_jobs) * 0.3:
            suggestions.append(
                f"스킬 제약조건 완화 권장 ({skills_issues}개 작업이 스킬 문제)"
            )

        if max_tasks_issues > 0:
            suggestions.append(
                f"max_tasks 증가 권장 ({max_tasks_issues}개 작업이 max_tasks 문제)"
            )

        if not suggestions:
            suggestions.append("차량 수 증가 또는 작업 분할 고려")

        return suggestions

    def auto_tune_for_unassigned(
        self,
        vrp_input: Dict[str, Any],
        unassigned_jobs: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        미배정 작업 기반 자동 튜닝

        미배정 사유를 분석하여 가장 적절한 완화 전략 자동 적용

        Args:
            vrp_input: VRP 입력
            unassigned_jobs: 미배정 작업 리스트

        Returns:
            튜닝된 VRP 입력
        """
        reasons = [job.get('reason', '') for job in unassigned_jobs]

        time_window_issues = sum(1 for r in reasons if 'time' in r.lower())
        capacity_issues = sum(1 for r in reasons if 'capacity' in r.lower())
        skills_issues = sum(1 for r in reasons if 'skill' in r.lower())

        tuned = vrp_input

        # 가장 많은 문제부터 해결
        if time_window_issues >= capacity_issues and time_window_issues >= skills_issues:
            logger.info("Auto-tuning: Relaxing time windows (primary issue)")
            tuned = self.strategy.relax_time_windows(tuned, 1.3)

        elif capacity_issues >= skills_issues:
            logger.info("Auto-tuning: Increasing vehicle capacity (primary issue)")
            tuned = self.strategy.increase_vehicle_capacity(tuned, 1.4)

        else:
            logger.info("Auto-tuning: Removing skills constraints (primary issue)")
            tuned = self.strategy.remove_skills_constraints(tuned)

        return tuned
