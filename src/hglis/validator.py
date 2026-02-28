"""
HGLIS 비즈니스 검증 (Step 1 + Step 2)

- 필수 필드 존재/타입 검증 (Pydantic이 대부분 처리)
- 비즈니스 규칙 사전 검증
- 오더/기사 분석 리포트 (수요-공급 매칭 가능성)
"""

import logging
from typing import List, Dict, Any
from .models import (
    HglisJob, HglisVehicle, HglisDispatchRequest,
    METRO_REGIONS, LOCAL_REGIONS, Grade, MONTHLY_CAP,
)

logger = logging.getLogger(__name__)

# C4 기능도 순서
GRADE_ORDER: Dict[str, int] = {"C": 1, "B": 2, "A": 3, "S": 4}


class ValidationResult:
    """검증 결과"""

    def __init__(self):
        self.errors: List[Dict[str, Any]] = []
        self.warnings: List[Dict[str, Any]] = []

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    def add_error(self, code: str, message: str, **kwargs):
        self.errors.append({"type": code, "message": message, **kwargs})

    def add_warning(self, code: str, message: str, **kwargs):
        self.warnings.append({"type": code, "message": message, **kwargs})

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "errors": self.errors,
            "warnings": self.warnings,
        }


def validate_request(request: HglisDispatchRequest) -> ValidationResult:
    """전체 요청 검증 (Pydantic 통과 후 비즈니스 규칙)"""
    result = ValidationResult()

    _validate_id_uniqueness(request, result)
    _validate_region_coverage(request, result)
    _validate_crew_supply(request, result)
    _validate_grade_supply(request, result)
    _validate_c6_capacity(request, result)
    _validate_sofa_coverage(request, result)

    if result.errors:
        logger.warning(f"검증 실패: {len(result.errors)}건 에러")
    if result.warnings:
        logger.info(f"검증 경고: {len(result.warnings)}건")

    return result


def _validate_id_uniqueness(request: HglisDispatchRequest, result: ValidationResult):
    """ID 중복 검사"""
    job_ids = [j.id for j in request.jobs]
    if len(job_ids) != len(set(job_ids)):
        dups = [x for x in job_ids if job_ids.count(x) > 1]
        result.add_error("DUPLICATE_JOB_ID", f"중복 오더 ID: {set(dups)}")

    vehicle_ids = [v.id for v in request.vehicles]
    if len(vehicle_ids) != len(set(vehicle_ids)):
        dups = [x for x in vehicle_ids if vehicle_ids.count(x) > 1]
        result.add_error("DUPLICATE_VEHICLE_ID", f"중복 기사 ID: {set(dups)}")


def _validate_region_coverage(request: HglisDispatchRequest, result: ValidationResult):
    """권역별 수요-공급 검증"""
    job_regions: Dict[str, int] = {}
    for j in request.jobs:
        job_regions[j.region_code] = job_regions.get(j.region_code, 0) + 1

    vehicle_regions: Dict[str, int] = {}
    for v in request.vehicles:
        vehicle_regions[v.region_code] = vehicle_regions.get(v.region_code, 0) + 1

    for region, count in job_regions.items():
        if region not in vehicle_regions:
            result.add_warning(
                "NO_VEHICLE_IN_REGION",
                f"권역 {region}에 오더 {count}건 있으나 기사 없음",
                region=region, job_count=count,
            )


def _validate_crew_supply(request: HglisDispatchRequest, result: ValidationResult):
    """C1: 2인 오더 대비 2인팀 공급 검증"""
    two_person_jobs = sum(1 for j in request.jobs if j.constraints.crew_type == "2인")
    two_person_vehicles = sum(1 for v in request.vehicles if v.crew.size == 2)
    filler_vehicles = sum(1 for v in request.vehicles if v.crew.size == 1 and v.crew.is_filler)

    if two_person_jobs > 0 and two_person_vehicles == 0 and filler_vehicles < 2:
        result.add_warning(
            "C1_CREW_SHORTAGE",
            f"2인 오더 {two_person_jobs}건이나 2인팀 없고 합배차 가능 기사 {filler_vehicles}명뿐",
            two_person_jobs=two_person_jobs,
            two_person_vehicles=two_person_vehicles,
            filler_vehicles=filler_vehicles,
        )


def _validate_grade_supply(request: HglisDispatchRequest, result: ValidationResult):
    """C4: 기능도별 수요-공급 검증"""
    # 오더 측: 제품 중 최고 필요기능도
    demand: Dict[str, int] = {"S": 0, "A": 0, "B": 0, "C": 0}
    for j in request.jobs:
        max_grade = max((p.required_grade for p in j.products), key=lambda g: GRADE_ORDER[g])
        demand[max_grade] += 1

    # 기사 측: 해당 등급 이상 처리 가능
    supply: Dict[str, int] = {"S": 0, "A": 0, "B": 0, "C": 0}
    for v in request.vehicles:
        supply[v.skill_grade] += 1

    # 상위 등급은 하위 처리 가능 → 누적
    cumulative_supply = 0
    cumulative_demand = 0
    for grade in ["S", "A", "B", "C"]:
        cumulative_supply += supply[grade]
        cumulative_demand += demand[grade]
        if cumulative_demand > cumulative_supply:
            result.add_warning(
                "C4_GRADE_SHORTAGE",
                f"기능도 {grade} 이상 오더 {cumulative_demand}건 vs 처리 가능 기사 {cumulative_supply}명",
                grade=grade,
                demand=cumulative_demand,
                supply=cumulative_supply,
            )


def _validate_c6_capacity(request: HglisDispatchRequest, result: ValidationResult):
    """C6: 월상한 여유 검증"""
    for v in request.vehicles:
        cap = MONTHLY_CAP.get(v.service_grade, 7_000_000)
        remaining = cap - v.fee_status.monthly_accumulated
        if remaining <= 0:
            result.add_warning(
                "C6_ALREADY_FULL",
                f"기사 {v.driver_id}: 월상한 이미 초과 (누적 {v.fee_status.monthly_accumulated:,} / 상한 {cap:,})",
                driver_id=v.driver_id,
                monthly_accumulated=v.fee_status.monthly_accumulated,
                cap=cap,
            )


def _validate_sofa_coverage(request: HglisDispatchRequest, result: ValidationResult):
    """소파 오더 vs W1/지방 기사 검증"""
    sofa_jobs = sum(
        1 for j in request.jobs
        if any(p.is_sofa for p in j.products)
    )
    if sofa_jobs == 0:
        return

    sofa_capable = sum(
        1 for v in request.vehicles
        if v.region_code == "W1" or v.region_code in LOCAL_REGIONS
    )

    if sofa_capable == 0:
        result.add_warning(
            "SOFA_NO_VEHICLE",
            f"소파 오더 {sofa_jobs}건이나 W1/지방 기사 없음",
            sofa_jobs=sofa_jobs,
        )
