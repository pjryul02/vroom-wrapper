"""
C6 월설치비 상한 검증 (후처리)

서비스등급 기준 월상한:
  S: 12,000,000원
  A: 11,000,000원
  B:  9,000,000원
  C:  7,000,000원

검증: 기존 누적 + 오늘 배정분 > 상한 → 경고
"""

import logging
from typing import List, Dict, Any
from .models import HglisVehicle, DriverSummary, MONTHLY_CAP

logger = logging.getLogger(__name__)


def validate_c6(
    driver_summaries: List[DriverSummary],
    vehicles: List[HglisVehicle],
) -> List[Dict[str, Any]]:
    """
    C6 월상한 검증.

    기사별로 (월누적 + 오늘 배정 설치비) vs 월상한 비교.

    Returns: 경고 목록
    """
    vehicle_map = {v.driver_id: v for v in vehicles}
    warnings = []

    for ds in driver_summaries:
        vehicle = vehicle_map.get(ds.driver_id)
        if not vehicle:
            continue

        cap = MONTHLY_CAP.get(vehicle.service_grade, MONTHLY_CAP["C"])
        monthly_before = vehicle.fee_status.monthly_accumulated
        monthly_after = monthly_before + ds.total_fee

        ds.c6_cap = cap
        ds.monthly_after = monthly_after

        if monthly_after > cap:
            ds.c6_status = "over"
            warnings.append({
                "type": "C6_MONTHLY_CAP_EXCEEDED",
                "driver_id": ds.driver_id,
                "driver_name": ds.driver_name,
                "message": (
                    f"기사 {ds.driver_id}: 월상한 초과 "
                    f"({monthly_after:,}원 / 상한 {cap:,}원, "
                    f"서비스등급 {vehicle.service_grade})"
                ),
                "monthly_before": monthly_before,
                "today_fee": ds.total_fee,
                "monthly_after": monthly_after,
                "cap": cap,
                "service_grade": vehicle.service_grade,
                "overflow": monthly_after - cap,
            })
        elif monthly_after > cap * 0.9:
            ds.c6_status = "warning"
            warnings.append({
                "type": "C6_MONTHLY_CAP_WARNING",
                "driver_id": ds.driver_id,
                "driver_name": ds.driver_name,
                "message": (
                    f"기사 {ds.driver_id}: 월상한 90% 도달 "
                    f"({monthly_after:,}원 / 상한 {cap:,}원)"
                ),
                "monthly_after": monthly_after,
                "cap": cap,
                "remaining": cap - monthly_after,
            })
        else:
            ds.c6_status = "ok"

    if warnings:
        logger.info(f"C6 월상한 경고: {len(warnings)}건")

    return warnings
