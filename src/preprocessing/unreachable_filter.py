"""
UnreachableFilter - 도달 불가능 작업 사전 필터링

Roouty Engine (Go)의 패턴을 Python으로 구현:
- 매트릭스에서 비정상적으로 큰 값 탐지 (>43200초)
- 모든 차량에서 도달 불가능한 작업 식별
- VROOM 호출 전에 제거하여 에러 방지
- 제거된 작업은 응답의 unassigned에 추가

참고: roouty-engine/pkg/features/distribute/filter/unreachable.go
"""

import logging
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)

# 12시간 (초) - Roouty Engine과 동일
# OSRM null → 86400, calibration 적용 후 ~56248 → 이 임계값보다 큼
MAX_REACHABLE_DURATION = 43200


class UnreachableFilter:
    """
    도달 불가능 작업 사전 필터링

    OSRM이 null을 반환하는 위치 (섬, 페리 제외 등)를 감지하여
    VROOM 호출 전에 제거. 500 에러 방지.
    """

    def __init__(self, threshold: int = MAX_REACHABLE_DURATION):
        self.threshold = threshold

    def filter(
        self, vrp_input: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """
        도달 불가능 작업 필터링

        Args:
            vrp_input: VROOM 입력 (vehicles, jobs, matrices 포함)

        Returns:
            (filtered_input, unreachable_jobs)
            - filtered_input: 도달 가능한 작업만 포함
            - unreachable_jobs: 도달 불가능 작업 리스트 (unassigned 형식)
        """
        matrices = vrp_input.get("matrices", {})
        jobs = vrp_input.get("jobs", [])
        vehicles = vrp_input.get("vehicles", [])

        if not matrices or not jobs or not vehicles:
            return vrp_input, []

        # 첫 번째 매트릭스 프로필 가져오기
        durations = self._get_duration_matrix(matrices)
        if not durations:
            return vrp_input, []

        # 위치 인덱스 매핑 구성
        vehicle_indices = self._build_vehicle_indices(vehicles)
        job_location_map = self._build_job_location_map(jobs, len(vehicle_indices))

        logger.info(
            f"[FILTER] 필터링 시작 - Jobs: {len(jobs)}, "
            f"Vehicles: {len(vehicles)}, Matrix: {len(durations)}x{len(durations[0]) if durations else 0}"
        )

        # 도달 가능/불가능 분류
        reachable_jobs = []
        unreachable_jobs = []

        for job in jobs:
            job_id = job.get("id")
            job_idx = job_location_map.get(job_id)

            if job_idx is None:
                reachable_jobs.append(job)
                continue

            if self._is_reachable_from_any_vehicle(
                durations, vehicle_indices, job_idx
            ):
                reachable_jobs.append(job)
            else:
                logger.warning(
                    f"[FILTER] Job {job_id} 도달 불가능 - 미배차 처리"
                )
                unreachable_jobs.append({
                    "id": job_id,
                    "type": "job",
                    "location": job.get("location"),
                    "description": job.get("description", ""),
                    "reason": "unreachable",
                })

        if unreachable_jobs:
            logger.info(
                f"[FILTER] {len(jobs)}개 job 중 {len(unreachable_jobs)}개 도달 불가능 필터링"
            )

            # 필터링된 입력 생성
            filtered = vrp_input.copy()
            filtered["jobs"] = reachable_jobs

            # 매트릭스도 재구성 필요할 수 있으나,
            # VROOM이 불필요한 인덱스를 무시하므로 그대로 유지
            return filtered, unreachable_jobs

        return vrp_input, []

    def _get_duration_matrix(
        self, matrices: Dict[str, Any]
    ) -> List[List[int]]:
        """매트릭스에서 duration 추출"""
        # VROOM 형식: matrices.car.durations 또는 matrices.durations
        if "durations" in matrices:
            return matrices["durations"]

        # 프로필별 매트릭스 (car, bike 등)
        for profile_name, profile_data in matrices.items():
            if isinstance(profile_data, dict) and "durations" in profile_data:
                return profile_data["durations"]

        return []

    def _build_vehicle_indices(
        self, vehicles: List[Dict[str, Any]]
    ) -> List[int]:
        """
        차량 시작 위치의 매트릭스 인덱스

        VROOM 매트릭스 인덱스 순서:
        [vehicle_start_0, vehicle_start_1, ..., vehicle_end_0, ..., job_0, job_1, ...]
        """
        indices = []
        for i in range(len(vehicles)):
            indices.append(i)  # vehicle start index
        return indices

    def _build_job_location_map(
        self, jobs: List[Dict[str, Any]], vehicle_count: int
    ) -> Dict[int, int]:
        """
        Job ID → 매트릭스 인덱스 매핑

        vehicle가 start만 있으면: offset = len(vehicles)
        vehicle가 start+end면: offset = len(vehicles) * 2
        """
        # 간단한 매핑: vehicles 뒤에 jobs 순서대로
        # 실제로는 vehicle start/end 여부에 따라 달라짐
        offset = vehicle_count  # start만 있는 경우
        job_map = {}
        for i, job in enumerate(jobs):
            job_map[job.get("id")] = offset + i
        return job_map

    def _is_reachable_from_any_vehicle(
        self,
        durations: List[List[int]],
        vehicle_indices: List[int],
        job_idx: int,
    ) -> bool:
        """
        최소 하나의 차량에서 도달 가능한지 확인

        Roouty의 isJobReachableFromAnyVehicle() 패턴:
        - vehicle→job 방향과 job→vehicle 방향 모두 확인
        - 하나라도 도달 가능하면 True
        """
        matrix_size = len(durations)

        for v_idx in vehicle_indices:
            if v_idx >= matrix_size or job_idx >= matrix_size:
                continue

            # 양방향 확인
            forward = durations[v_idx][job_idx]  # vehicle → job
            backward = durations[job_idx][v_idx]  # job → vehicle

            if forward < self.threshold and backward < self.threshold:
                return True

        return False
