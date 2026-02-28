"""
권역 분할기 — 권역별 독립 VROOM 실행 + 결과 병합

strict 모드: 권역 정확히 분리, 교차 불가
flexible 모드: 권역별 분리하되, 미배정은 인접 권역에 재시도
ignore 모드: 전체를 하나의 VROOM 호출로 처리
"""

import asyncio
import logging
from typing import List, Dict, Any, Tuple

from .models import (
    HglisJob, HglisVehicle, HglisDispatchRequest, DispatchOptions,
    METRO_REGIONS, LOCAL_REGIONS,
)

logger = logging.getLogger(__name__)


def split_by_region(
    request: HglisDispatchRequest,
) -> Dict[str, Tuple[List[HglisJob], List[HglisVehicle]]]:
    """
    권역별로 오더와 기사를 분리.

    Returns: { region_code: (jobs, vehicles) }
    """
    if request.meta.region_mode == "ignore":
        # 전체를 "ALL" 하나의 그룹으로
        return {"ALL": (list(request.jobs), list(request.vehicles))}

    region_jobs: Dict[str, List[HglisJob]] = {}
    region_vehicles: Dict[str, List[HglisVehicle]] = {}

    for job in request.jobs:
        region = _normalize_region(job.region_code)
        region_jobs.setdefault(region, []).append(job)

    for vehicle in request.vehicles:
        region = _normalize_region(vehicle.region_code)
        region_vehicles.setdefault(region, []).append(vehicle)

    result = {}
    all_regions = set(region_jobs.keys()) | set(region_vehicles.keys())

    for region in all_regions:
        jobs = region_jobs.get(region, [])
        vehicles = region_vehicles.get(region, [])
        if jobs:  # 오더가 있는 권역만 포함
            result[region] = (jobs, vehicles)

    logger.info(
        f"권역 분할: {len(result)}개 그룹 "
        f"({', '.join(f'{k}:{len(v[0])}j/{len(v[1])}v' for k, v in result.items())})"
    )

    return result


def _normalize_region(region_code: str) -> str:
    """
    권역 코드 정규화.

    경인권: Y1, Y2, Y3, Y5 → 각각 독립 유지
    W1: 소파 전용 독립
    지방: 각각 독립
    """
    return region_code


def merge_vroom_results(
    region_results: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """
    권역별 VROOM 결과를 하나로 병합.

    Returns: 병합된 VROOM-like result dict
    """
    merged = {
        "code": 0,
        "routes": [],
        "unassigned": [],
        "summary": {
            "cost": 0,
            "routes": 0,
            "unassigned": 0,
            "setup": 0,
            "service": 0,
            "duration": 0,
            "waiting_time": 0,
            "distance": 0,
        },
    }

    for region, result in region_results.items():
        if result.get("code", 0) != 0:
            logger.warning(f"권역 {region} VROOM 오류: code={result.get('code')}")

        for route in result.get("routes", []):
            route["_region"] = region  # 추적용 태그
            merged["routes"].append(route)

        for ua in result.get("unassigned", []):
            ua["_region"] = region
            merged["unassigned"].append(ua)

        summary = result.get("summary", {})
        merged["summary"]["cost"] += summary.get("cost", 0)
        merged["summary"]["routes"] += summary.get("routes", 0)
        merged["summary"]["unassigned"] += summary.get("unassigned", 0)
        merged["summary"]["setup"] += summary.get("setup", 0)
        merged["summary"]["service"] += summary.get("service", 0)
        merged["summary"]["duration"] += summary.get("duration", 0)
        merged["summary"]["waiting_time"] += summary.get("waiting_time", 0)
        merged["summary"]["distance"] += summary.get("distance", 0)

    logger.info(
        f"결과 병합: {len(region_results)}개 권역, "
        f"routes={len(merged['routes'])}, unassigned={len(merged['unassigned'])}"
    )

    return merged
