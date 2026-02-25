"""
Constraint Checker - 미배정 사유 분석 (v1.0 → v3.0 통합)

VROOM은 미배정(unassigned) 작업에 대해 사유를 제공하지 않음.
이 모듈은 원본 입력과 비교하여 미배정 사유를 역추적함.

검사 항목:
  - skills: 차량 스킬 불일치
  - capacity: 용량 초과
  - time_window: 시간대 불일치
  - max_tasks: 최대 작업수 초과
  - vehicle_time_window: 차량 운행시간 초과
  - no_vehicles: 가용 차량 없음
  - complex_constraint: 복합 제약 (단일 원인 특정 불가)
"""

from typing import List, Dict, Any
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ViolationType(str, Enum):
    SKILLS = "skills"
    CAPACITY = "capacity"
    TIME_WINDOW = "time_window"
    MAX_TASKS = "max_tasks"
    VEHICLE_TIME_WINDOW = "vehicle_time_window"
    PRECEDENCE = "precedence"
    NO_VEHICLES = "no_vehicles"


SKILL_NAMES: Dict[int, str] = {
    10000: "VIP",
    10001: "긴급(Urgent)",
    20000: "서울 지역",
    20001: "부산 지역",
    20002: "인천 지역",
    20003: "대구 지역",
    20004: "대전 지역",
    20005: "광주 지역",
    20006: "울산 지역",
}


def _skill_label(skill_id: int) -> str:
    """스킬 번호를 사람이 읽을 수 있는 이름으로 변환"""
    name = SKILL_NAMES.get(skill_id)
    if name:
        return f"{name}({skill_id})"
    return str(skill_id)


def _skill_labels(skill_ids: set) -> List[str]:
    return [_skill_label(s) for s in sorted(skill_ids)]


class ConstraintChecker:
    """Analyzes why jobs are unassigned by comparing with original input"""

    def __init__(self, vrp_input: Dict[str, Any]):
        self.vehicles = vrp_input.get('vehicles', [])
        self.jobs = vrp_input.get('jobs', [])
        self.shipments = vrp_input.get('shipments', [])
        self.jobs_by_id = {job['id']: job for job in self.jobs}
        self.shipments_by_id = {s.get('id', i): s for i, s in enumerate(self.shipments)}

    def analyze_unassigned(self, unassigned_list: List[Dict]) -> Dict[int, List[Dict]]:
        """
        For each unassigned job/shipment, determine why it couldn't be assigned.

        Returns:
            Dict mapping job/shipment ID to list of violation reasons
        """
        reasons_map = {}

        for unassigned in unassigned_list:
            job_id = unassigned.get('id')
            if job_id is None:
                continue

            # unreachable 필터에서 이미 사유가 있으면 스킵
            if unassigned.get('reason') == 'unreachable':
                reasons_map[job_id] = [{
                    "type": "unreachable",
                    "description": "도달 불가능한 위치 (모든 차량에서 이동 시간 초과)",
                    "details": {}
                }]
                continue

            job_type = unassigned.get('type', 'job')

            if job_type == 'job':
                job = self.jobs_by_id.get(job_id)
                if job:
                    reasons = self._check_job_violations(job)
                else:
                    reasons = [{"type": "unknown", "description": "Job not found in input", "details": {}}]
            else:
                shipment = self.shipments_by_id.get(job_id)
                if shipment:
                    reasons = self._check_shipment_violations(shipment)
                else:
                    reasons = [{"type": "unknown", "description": "Shipment not found in input", "details": {}}]

            reasons_map[job_id] = reasons

        return reasons_map

    def _check_job_violations(self, job: Dict) -> List[Dict]:
        """Check why a job couldn't be assigned to any vehicle"""
        violations = []

        if not self.vehicles:
            violations.append({
                "type": ViolationType.NO_VEHICLES,
                "description": "가용 차량 없음",
                "details": {}
            })
            return violations

        job_skills = set(job.get('skills', []))
        job_delivery = job.get('delivery', job.get('amount', [0]))
        job_pickup = job.get('pickup', [0])
        job_time_windows = job.get('time_windows', [])

        # 1. Skills 호환성 검사
        skills_compatible = []
        for vehicle in self.vehicles:
            vehicle_skills = set(vehicle.get('skills', []))
            if not job_skills or job_skills.issubset(vehicle_skills):
                skills_compatible.append(vehicle)

        if not skills_compatible:
            missing_labels = _skill_labels(job_skills)
            violations.append({
                "type": ViolationType.SKILLS,
                "description": f"필요 스킬을 가진 차량 없음: {', '.join(missing_labels)}",
                "details": {
                    "required_skills": list(job_skills),
                    "required_skill_names": missing_labels,
                    "available_vehicle_skills": [v.get('skills', []) for v in self.vehicles]
                }
            })
            return violations

        # 2. Capacity 검사
        capacity_compatible = []
        for vehicle in skills_compatible:
            vehicle_capacity = vehicle.get('capacity', [])
            if not vehicle_capacity:
                capacity_compatible.append(vehicle)
                continue

            can_handle = True
            load = job_delivery if job_delivery else job_pickup
            for i, demand in enumerate(load):
                if i < len(vehicle_capacity) and demand > vehicle_capacity[i]:
                    can_handle = False
                    break

            if can_handle:
                capacity_compatible.append(vehicle)

        if not capacity_compatible:
            violations.append({
                "type": ViolationType.CAPACITY,
                "description": "모든 호환 차량의 용량 초과",
                "details": {
                    "job_delivery": job_delivery,
                    "job_pickup": job_pickup,
                    "vehicle_capacities": [v.get('capacity', []) for v in skills_compatible]
                }
            })
            return violations

        # 3. Time Window 검사
        time_window_ok = False
        if job_time_windows:
            for vehicle in capacity_compatible:
                vehicle_tw = vehicle.get('time_window')
                if not vehicle_tw:
                    time_window_ok = True
                    break
                for job_tw in job_time_windows:
                    if len(job_tw) >= 2 and job_tw[0] <= vehicle_tw[1] and job_tw[1] >= vehicle_tw[0]:
                        time_window_ok = True
                        break
                if time_window_ok:
                    break
        else:
            time_window_ok = True

        if not time_window_ok:
            violations.append({
                "type": ViolationType.TIME_WINDOW,
                "description": "작업 시간대와 호환되는 차량 없음",
                "details": {
                    "job_time_windows": job_time_windows,
                    "vehicle_time_windows": [
                        v.get('time_window') for v in capacity_compatible if v.get('time_window')
                    ]
                }
            })

        # 4. Max Tasks 검사
        max_tasks_info = []
        for vehicle in capacity_compatible:
            max_tasks = vehicle.get('max_tasks')
            if max_tasks is not None:
                max_tasks_info.append({"vehicle_id": vehicle['id'], "max_tasks": max_tasks})

        if max_tasks_info and not violations:
            violations.append({
                "type": ViolationType.MAX_TASKS,
                "description": "호환 차량들의 최대 작업수 한도 도달 가능",
                "details": {"vehicles_with_limits": max_tasks_info}
            })

        # 5. 특정 사유 못 찾으면 복합 제약
        if not violations:
            violations.append({
                "type": "complex_constraint",
                "description": "복합 제약으로 인한 미배정 (시간대, 경로 최적화, 차량 부하 등 조합)",
                "details": {
                    "compatible_vehicles_count": len(capacity_compatible),
                    "note": "이론적으로 호환되나 최적 경로에 포함 불가"
                }
            })

        return violations

    def _check_shipment_violations(self, shipment: Dict) -> List[Dict]:
        """Check why a shipment couldn't be assigned"""
        violations = []

        pickup = shipment.get('pickup', {})
        delivery = shipment.get('delivery', {})

        pickup_skills = set(pickup.get('skills', []))
        delivery_skills = set(delivery.get('skills', []))

        if pickup_skills != delivery_skills:
            violations.append({
                "type": ViolationType.SKILLS,
                "description": f"픽업과 배달의 스킬 요구가 다름: 픽업={_skill_labels(pickup_skills)}, 배달={_skill_labels(delivery_skills)}",
                "details": {
                    "pickup_skills": list(pickup_skills),
                    "pickup_skill_names": _skill_labels(pickup_skills),
                    "delivery_skills": list(delivery_skills),
                    "delivery_skill_names": _skill_labels(delivery_skills),
                }
            })

        return violations if violations else [{
            "type": "complex_constraint",
            "description": "복합 제약으로 인한 미배정",
            "details": {}
        }]
