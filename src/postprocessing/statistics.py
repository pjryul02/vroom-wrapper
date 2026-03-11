#!/usr/bin/env python3
"""
StatisticsGenerator - 통계 생성

Phase 3/5: 결과 통계 및 비용 계산
"""

from typing import Dict, List, Any
import logging

logger = logging.getLogger(__name__)


class StatisticsGenerator:
    """VROOM 결과 통계 생성"""

    def generate(
        self,
        vrp_input: Dict[str, Any],
        vroom_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        통계 생성

        Returns:
            {
                'vehicle_utilization': {...},
                'cost_breakdown': {...},
                'time_analysis': {...},
                'efficiency_metrics': {...}
            }
        """
        return {
            'vehicle_utilization': self._calculate_vehicle_utilization(vroom_result),
            'cost_breakdown': self._calculate_cost_breakdown(vroom_result),
            'time_analysis': self._analyze_time(vroom_result),
            'efficiency_metrics': self._calculate_efficiency(vrp_input, vroom_result)
        }

    def _calculate_vehicle_utilization(self, vroom_result: Dict[str, Any]) -> Dict:
        """차량 활용도 계산"""
        routes = vroom_result.get('routes', [])

        utilization = []
        for route in routes:
            vehicle_id = route.get('vehicle')
            num_jobs = sum(1 for s in route.get('steps', []) if s.get('type') == 'job')
            distance = route.get('distance', 0)
            duration = route.get('duration', 0)
            capacity_used = sum(route.get('amount', []))

            utilization.append({
                'vehicle': vehicle_id,
                'jobs': num_jobs,
                'distance_km': round(distance / 1000, 2),
                'duration_min': round(duration / 60, 1),
                'capacity_used': capacity_used
            })

        return {'vehicles': utilization}

    def _calculate_cost_breakdown(self, vroom_result: Dict[str, Any]) -> Dict:
        """비용 분석"""
        summary = vroom_result.get('summary', {})

        return {
            'total_cost': summary.get('cost', 0),
            'total_distance_km': round(summary.get('distance', 0) / 1000, 2),
            'total_duration_hours': round(summary.get('duration', 0) / 3600, 2),
            'service_time_hours': round(summary.get('service', 0) / 3600, 2),
            'waiting_time_hours': round(summary.get('waiting_time', 0) / 3600, 2)
        }

    def _analyze_time(self, vroom_result: Dict[str, Any]) -> Dict:
        """시간 분석"""
        summary = vroom_result.get('summary', {})

        # VROOM의 duration은 순수 이동시간만 포함 (service/waiting 별도)
        travel_time = summary.get('duration', 0)
        service_time = summary.get('service', 0)
        waiting_time = summary.get('waiting_time', 0)
        total_time = travel_time + service_time + waiting_time

        return {
            'total_duration_sec': total_time,
            'travel_time_sec': travel_time,
            'service_time_sec': service_time,
            'waiting_time_sec': waiting_time,
            'travel_percentage': round(travel_time / total_time * 100, 1) if total_time > 0 else 0
        }

    def _calculate_efficiency(
        self,
        vrp_input: Dict[str, Any],
        vroom_result: Dict[str, Any]
    ) -> Dict:
        """효율성 지표"""
        total_jobs = len(vrp_input.get('jobs', [])) + len(vrp_input.get('shipments', []))
        num_vehicles = len(vrp_input.get('vehicles', []))
        total_distance = vroom_result.get('summary', {}).get('distance', 0)
        total_duration = vroom_result.get('summary', {}).get('duration', 0)

        return {
            'jobs_per_vehicle': round(total_jobs / num_vehicles, 2) if num_vehicles > 0 else 0,
            'km_per_job': round(total_distance / 1000 / total_jobs, 2) if total_jobs > 0 else 0,
            'minutes_per_job': round(total_duration / 60 / total_jobs, 1) if total_jobs > 0 else 0
        }
