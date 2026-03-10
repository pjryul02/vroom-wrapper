"""
HGLIS → VROOM JSON 조립

전처리된 데이터를 VROOM 표준 입력 포맷으로 변환.
"""

import math
import logging
from typing import List, Dict, Any, Optional
from .models import HglisJob, HglisVehicle, HglisDispatchRequest
from .skill_encoder import SkillEncodeResult
from .time_converter import (
    convert_job_time_windows,
    convert_vehicle_time_window,
    convert_vehicle_breaks,
    calc_service_seconds,
    calc_setup_seconds,
)

logger = logging.getLogger(__name__)

# C5: CBM → VROOM capacity 변환 배율 (소수 2자리 보존)
CBM_MULTIPLIER = 100

# priority 가중치
PRIORITY_URGENT = 100
PRIORITY_VIP = 50
PRIORITY_TWO_PERSON = 10
PRIORITY_MAX = 100

# 기사 활성화 고정 비용 (VROOM costs.fixed) — 기사 분산 유도
VEHICLE_FIXED_COST = 1000


def assemble_vroom_input(
    request: HglisDispatchRequest,
    skill_result: SkillEncodeResult,
) -> Dict[str, Any]:
    """
    HGLIS 요청 → VROOM JSON 조립

    Returns: VROOM 호환 JSON dict
    """
    base_date = request.meta.date

    # max_tasks 동적 계산: min(사용자 설정, ceil(오더/기사) + 2)
    num_jobs = len(request.jobs)
    num_vehicles = len(request.vehicles)
    user_max = request.options.max_tasks_per_driver
    if num_vehicles > 0:
        dynamic_max = math.ceil(num_jobs / num_vehicles) + 2
        effective_max = min(user_max, dynamic_max)
    else:
        effective_max = user_max

    vroom_jobs = []
    for job in request.jobs:
        vj = _build_vroom_job(job, base_date, skill_result)
        vroom_jobs.append(vj)

    vroom_vehicles = []
    for vehicle in request.vehicles:
        vv = _build_vroom_vehicle(vehicle, base_date, skill_result, effective_max)
        vroom_vehicles.append(vv)

    vroom_input = {
        "jobs": vroom_jobs,
        "vehicles": vroom_vehicles,
        "options": {"g": request.options.geometry},
    }

    logger.info(
        f"VROOM JSON 조립 완료: jobs={len(vroom_jobs)}, vehicles={len(vroom_vehicles)}"
    )

    return vroom_input


def _build_vroom_job(
    job: HglisJob,
    base_date: str,
    skill_result: SkillEncodeResult,
) -> Dict[str, Any]:
    """개별 오더 → VROOM job"""

    # description
    customer_name = ""
    if job.customer and job.customer.name:
        customer_name = f"_{job.customer.name}"
    description = f"{job.order_id}{customer_name}"

    # C5: CBM → delivery
    total_cbm = sum(p.cbm * p.quantity for p in job.products)
    delivery = [int(total_cbm * CBM_MULTIPLIER), 0, 0]

    # C3: time_windows
    time_windows = convert_job_time_windows(job, base_date)

    # skills
    skills = skill_result.job_skills.get(job.id, [])

    # service
    service = calc_service_seconds(job)

    # setup
    setup = calc_setup_seconds(job)

    # priority
    priority = _calc_priority(job)

    vroom_job: Dict[str, Any] = {
        "id": job.id,
        "description": description,
        "location": job.location,
        "service": service,
        "delivery": delivery,
        "skills": skills,
        "time_windows": time_windows,
        "priority": priority,
    }

    if setup:
        vroom_job["setup"] = setup

    return vroom_job


def _build_vroom_vehicle(
    vehicle: HglisVehicle,
    base_date: str,
    skill_result: SkillEncodeResult,
    max_tasks: int,
) -> Dict[str, Any]:
    """개별 기사 → VROOM vehicle"""

    # description
    driver_name = vehicle.driver_name or ""
    description = f"{vehicle.driver_id}_{driver_name}".rstrip("_")

    # C5: capacity
    capacity = [int(vehicle.capacity_cbm * CBM_MULTIPLIER), 0, 0]

    # time_window
    time_window = convert_vehicle_time_window(vehicle, base_date)

    # skills
    skills = skill_result.vehicle_skills.get(vehicle.id, [])

    # breaks
    breaks = convert_vehicle_breaks(vehicle, base_date)

    vroom_vehicle: Dict[str, Any] = {
        "id": vehicle.id,
        "description": description,
        "start": vehicle.location.start,
        "end": vehicle.location.end,
        "capacity": capacity,
        "skills": skills,
        "time_window": time_window,
        "max_tasks": max_tasks,
        "costs": {"fixed": VEHICLE_FIXED_COST},
    }

    if breaks:
        vroom_vehicle["breaks"] = breaks

    return vroom_vehicle


def _calc_priority(job: HglisJob) -> int:
    """오더 우선순위 계산 (0~100)"""
    p = job.priority.level
    if job.priority.is_urgent:
        p += PRIORITY_URGENT
    if job.priority.is_vip:
        p += PRIORITY_VIP
    if job.constraints.crew_type == "2인":
        p += PRIORITY_TWO_PERSON
    return min(p, PRIORITY_MAX)
