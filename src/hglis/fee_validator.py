"""
C2 설치비 하한 검증 (후처리)

기사 일일 수익 = 설치비 합 + 거리비
거리비 = OSRM 실거리(물류센터→최원거리 배송지) 기반 테이블 조회

하한 기준:
  2인팀: 400,000원
  S등급: 280,000원
  A등급: 250,000원
  B등급: 220,000원
  C등급: 180,000원
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from .models import HglisVehicle, DriverSummary

logger = logging.getLogger(__name__)

# C2 설치비 하한 (원)
FEE_THRESHOLD: Dict[str, int] = {
    "2인팀": 400_000,
    "S": 280_000,
    "A": 250_000,
    "B": 220_000,
    "C": 180_000,
}

# 거리비 테이블 — 수도권 (km, 원)
DISTANCE_FEE_METRO: List[Tuple[int, int]] = [
    (30, 0),
    (50, 24_000),
    (70, 36_500),
    (100, 48_000),
    (150, 81_000),
    (999, 81_000),
]

# 거리비 테이블 — 지방 (km, 원)
DISTANCE_FEE_LOCAL: List[Tuple[int, int]] = [
    (70, 0),
    (100, 40_500),
    (150, 81_000),
    (200, 93_000),
    (999, 118_000),
]

METRO_REGIONS = {"Y1", "Y2", "Y3", "Y5", "W1"}


def lookup_distance_fee(distance_km: float, region_code: str) -> int:
    """거리비 테이블 조회"""
    table = DISTANCE_FEE_METRO if region_code in METRO_REGIONS else DISTANCE_FEE_LOCAL

    for max_km, fee in table:
        if distance_km <= max_km:
            return fee

    return table[-1][1]


def get_threshold(vehicle: HglisVehicle) -> int:
    """기사별 C2 하한 기준액"""
    if vehicle.crew.size == 2:
        return FEE_THRESHOLD["2인팀"]
    return FEE_THRESHOLD.get(vehicle.grade, FEE_THRESHOLD["C"])


def validate_c2(
    driver_summaries: List[DriverSummary],
    vehicles: List[HglisVehicle],
    vroom_result: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    C2 설치비 하한 검증.

    각 기사의 (설치비 합 + 거리비) >= 하한 여부 확인.
    거리비 계산: VROOM route의 distance (미터) → km → 테이블 조회.

    Returns: 경고 목록
    """
    vehicle_map = {v.driver_id: v for v in vehicles}
    route_distances: Dict[int, float] = {}  # vehicle_id → distance_km

    # VROOM route에서 거리 추출
    for route in vroom_result.get("routes", []):
        vid = route.get("vehicle")
        dist_m = route.get("distance", 0)
        route_distances[vid] = dist_m / 1000

    warnings = []

    for ds in driver_summaries:
        if ds.assigned_count == 0:
            continue

        vehicle = vehicle_map.get(ds.driver_id)
        if not vehicle:
            continue

        threshold = get_threshold(vehicle)
        distance_km = route_distances.get(vehicle.id, 0)
        distance_fee = lookup_distance_fee(distance_km, vehicle.region_code)

        daily_income = ds.total_fee + distance_fee

        # DriverSummary에 C2 정보 업데이트
        ds.c2_threshold = threshold
        if daily_income < threshold:
            ds.c2_status = "warning"
            warnings.append({
                "type": "C2_FEE_BELOW_THRESHOLD",
                "driver_id": ds.driver_id,
                "driver_name": ds.driver_name,
                "message": (
                    f"기사 {ds.driver_id}: 일일수익 {daily_income:,}원 "
                    f"(설치비 {ds.total_fee:,} + 거리비 {distance_fee:,}) < "
                    f"하한 {threshold:,}원"
                ),
                "daily_income": daily_income,
                "install_fee": ds.total_fee,
                "distance_fee": distance_fee,
                "distance_km": round(distance_km, 1),
                "threshold": threshold,
            })
        else:
            ds.c2_status = "ok"

    if warnings:
        logger.info(f"C2 설치비 하한 경고: {len(warnings)}건")

    return warnings
