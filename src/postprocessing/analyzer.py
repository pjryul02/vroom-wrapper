#!/usr/bin/env python3
"""
ResultAnalyzer - VROOM 결과 분석

Phase 3.2: 품질 점수, 미배정 사유, 개선 제안
"""

from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)


class ResultAnalyzer:
    """VROOM 결과 분석 및 품질 평가"""

    def analyze(
        self,
        vrp_input: Dict[str, Any],
        vroom_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        VROOM 결과 종합 분석

        Args:
            vrp_input: 원본 VRP 입력
            vroom_result: VROOM 결과

        Returns:
            분석 리포트
        """
        analysis = {
            'quality_score': self._calculate_quality_score(vrp_input, vroom_result),
            'assignment_rate': self._calculate_assignment_rate(vrp_input, vroom_result),
            'route_balance': self._analyze_route_balance(vroom_result),
            'time_window_utilization': self._analyze_time_window_utilization(vroom_result),
            'suggestions': self._generate_suggestions(vrp_input, vroom_result)
        }

        return analysis

    def _calculate_quality_score(
        self,
        vrp_input: Dict[str, Any],
        vroom_result: Dict[str, Any]
    ) -> float:
        """
        품질 점수 계산 (0-100)

        고려 요소:
        - 배정률 (40%)
        - 경로 균형도 (30%)
        - 시간창 활용도 (20%)
        - 비용 효율성 (10%)
        """
        # 1. 배정률 (0-40점)
        assignment_score = self._calculate_assignment_rate(vrp_input, vroom_result) * 0.4

        # 2. 경로 균형도 (0-30점)
        balance_score = self._calculate_balance_score(vroom_result) * 0.3

        # 3. 시간창 활용도 (0-20점)
        tw_score = self._calculate_tw_utilization_score(vroom_result) * 0.2

        # 4. 비용 효율성 (0-10점)
        cost_score = self._calculate_cost_efficiency_score(vrp_input, vroom_result) * 0.1

        total_score = assignment_score + balance_score + tw_score + cost_score

        logger.info(
            f"Quality score: {total_score:.1f} "
            f"(assignment={assignment_score:.1f}, "
            f"balance={balance_score:.1f}, "
            f"tw={tw_score:.1f}, "
            f"cost={cost_score:.1f})"
        )

        return round(total_score, 1)

    def _calculate_assignment_rate(
        self,
        vrp_input: Dict[str, Any],
        vroom_result: Dict[str, Any]
    ) -> float:
        """배정률 계산 (0-100)"""
        total_jobs = len(vrp_input.get('jobs', [])) + len(vrp_input.get('shipments', []))
        unassigned = len(vroom_result.get('unassigned', []))

        if total_jobs == 0:
            return 100.0

        assigned = total_jobs - unassigned
        rate = (assigned / total_jobs) * 100

        return round(rate, 2)

    def _calculate_balance_score(self, vroom_result: Dict[str, Any]) -> float:
        """경로 균형도 점수 (0-100)"""
        routes = vroom_result.get('routes', [])

        if len(routes) <= 1:
            return 100.0

        # 각 경로의 작업 수
        route_job_counts = []
        for route in routes:
            job_count = sum(
                1 for step in route.get('steps', [])
                if step.get('type') == 'job'
            )
            route_job_counts.append(job_count)

        if not route_job_counts or max(route_job_counts) == 0:
            return 100.0

        # 표준편차 계산 (간단 버전)
        avg = sum(route_job_counts) / len(route_job_counts)
        variance = sum((x - avg) ** 2 for x in route_job_counts) / len(route_job_counts)
        std_dev = variance ** 0.5

        # 변동계수 (CV)
        if avg == 0:
            return 100.0

        cv = std_dev / avg

        # CV가 낮을수록 균형이 좋음 (CV=0 → 100점, CV=1 → 0점)
        score = max(0, 100 * (1 - cv))

        return round(score, 2)

    def _calculate_tw_utilization_score(self, vroom_result: Dict[str, Any]) -> float:
        """시간창 활용도 점수 (0-100)"""
        # 간단 구현: 미배정이 없으면 100점
        unassigned = len(vroom_result.get('unassigned', []))

        if unassigned == 0:
            return 100.0
        else:
            return max(0, 100 - unassigned * 5)

    def _calculate_cost_efficiency_score(
        self,
        vrp_input: Dict[str, Any],
        vroom_result: Dict[str, Any]
    ) -> float:
        """비용 효율성 점수 (0-100)"""
        # 간단 구현: 작업당 비용 비율
        total_jobs = len(vrp_input.get('jobs', [])) + len(vrp_input.get('shipments', []))
        total_cost = vroom_result.get('summary', {}).get('cost', 0)

        if total_jobs == 0 or total_cost == 0:
            return 100.0

        cost_per_job = total_cost / total_jobs

        # 임계값 기준 (예: 작업당 10000 이하면 100점)
        threshold = 10000
        score = max(0, 100 * (1 - (cost_per_job / threshold)))

        return round(min(100, score), 2)

    def _analyze_route_balance(self, vroom_result: Dict[str, Any]) -> Dict[str, Any]:
        """경로 균형도 분석"""
        routes = vroom_result.get('routes', [])

        route_stats = []
        for route in routes:
            jobs = [s for s in route.get('steps', []) if s.get('type') == 'job']
            duration = route.get('duration', 0)
            distance = route.get('distance', 0)

            route_stats.append({
                'vehicle': route.get('vehicle'),
                'num_jobs': len(jobs),
                'duration': duration,
                'distance': distance
            })

        return {
            'routes': route_stats,
            'balance_score': self._calculate_balance_score(vroom_result)
        }

    def _analyze_time_window_utilization(self, vroom_result: Dict[str, Any]) -> Dict[str, Any]:
        """시간창 활용도 분석"""
        routes = vroom_result.get('routes', [])

        utilization = []
        for route in routes:
            steps = route.get('steps', [])

            if len(steps) < 2:
                continue

            start_time = steps[0].get('arrival', 0) if steps[0].get('arrival') is not None else 0
            end_time = steps[-1].get('arrival', 0) if steps[-1].get('arrival') is not None else 0

            duration = end_time - start_time

            utilization.append({
                'vehicle': route.get('vehicle'),
                'start_time': start_time,
                'end_time': end_time,
                'duration': duration
            })

        return {'utilization': utilization}

    def _generate_suggestions(
        self,
        vrp_input: Dict[str, Any],
        vroom_result: Dict[str, Any]
    ) -> List[str]:
        """개선 제안 생성"""
        suggestions = []

        # 배정률이 낮으면
        assignment_rate = self._calculate_assignment_rate(vrp_input, vroom_result)
        if assignment_rate < 80:
            suggestions.append(
                f"배정률이 낮습니다 ({assignment_rate:.1f}%). "
                "차량 수 증가 또는 제약조건 완화를 고려하세요."
            )

        # 경로 불균형
        balance_score = self._calculate_balance_score(vroom_result)
        if balance_score < 70:
            suggestions.append(
                f"경로 균형도가 낮습니다 ({balance_score:.1f}%). "
                "작업 분배를 개선하거나 차량 용량을 조정하세요."
            )

        # 미배정 작업
        unassigned = vroom_result.get('unassigned', [])
        if unassigned:
            suggestions.append(
                f"{len(unassigned)}개 작업이 미배정되었습니다. "
                "제약조건 완화 또는 차량 추가를 시도하세요."
            )

        # 제안이 없으면 긍정적 피드백
        if not suggestions:
            suggestions.append("최적화 결과가 우수합니다!")

        return suggestions
