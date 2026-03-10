"""
VroomMatrixPreparer - VROOM 입력에 OSRM 매트릭스 주입

조립된 VROOM JSON을 받아:
1. 모든 고유 좌표 수집 (vehicles start/end, jobs location)
2. OSRMChunkedMatrix로 OSRM Table API 1회 호출
3. 각 좌표 → 매트릭스 인덱스 매핑
4. jobs에 location_index, vehicles에 start_index/end_index 추가
5. matrices.car.durations/distances 추가

이를 통해:
- UnreachableFilter 동작 (matrices 키 존재)
- 2-Pass에서 OSRM 재호출 없이 서브매트릭스 추출
- VROOM이 OSRM을 직접 호출하지 않음 (매트릭스 사용)
"""

import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from .chunked_matrix import OSRMChunkedMatrix

logger = logging.getLogger(__name__)


class VroomMatrixPreparer:
    """VROOM 입력에 pre-computed OSRM 매트릭스를 주입"""

    def __init__(
        self,
        osrm_matrix: OSRMChunkedMatrix,
        profile: str = "car",
    ):
        self.osrm_matrix = osrm_matrix
        self.profile = profile

    async def prepare(
        self,
        vroom_input: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        VROOM 입력에 매트릭스 + 인덱스 추가 (in-place 수정).

        - vehicles[].start/end → start_index/end_index 추가
        - jobs[].location → location_index 추가
        - matrices: {"car": {"durations": [...], "distances": [...]}} 추가
        - 원본 location/start/end 필드는 유지 (geometry 생성용)

        Args:
            vroom_input: assemble_vroom_input() 결과물

        Returns:
            매트릭스 + 인덱스가 추가된 동일 dict
        """
        start_time = time.time()

        # 1. 모든 고유 좌표 수집 + 인덱스 매핑
        locations, coord_to_index = self._collect_unique_locations(vroom_input)

        if len(locations) < 2:
            logger.warning("[MATRIX_PREP] 좌표 2개 미만 - 매트릭스 생략")
            return vroom_input

        # 2. OSRM 매트릭스 계산
        logger.info(f"[MATRIX_PREP] {len(locations)}개 좌표 매트릭스 계산 시작")
        matrix_result = await self.osrm_matrix.build_matrix(
            locations, profile="driving",
        )

        # 3. vehicles에 start_index/end_index 추가
        for vehicle in vroom_input.get("vehicles", []):
            if "start" in vehicle:
                key = self._coord_key(vehicle["start"])
                vehicle["start_index"] = coord_to_index[key]
            if "end" in vehicle:
                key = self._coord_key(vehicle["end"])
                vehicle["end_index"] = coord_to_index[key]

        # 4. jobs에 location_index 추가
        for job in vroom_input.get("jobs", []):
            if "location" in job:
                key = self._coord_key(job["location"])
                job["location_index"] = coord_to_index[key]

        # 5. shipments에 pickup/delivery location_index 추가
        for shipment in vroom_input.get("shipments", []):
            if "pickup" in shipment and "location" in shipment["pickup"]:
                key = self._coord_key(shipment["pickup"]["location"])
                shipment["pickup"]["location_index"] = coord_to_index[key]
            if "delivery" in shipment and "location" in shipment["delivery"]:
                key = self._coord_key(shipment["delivery"]["location"])
                shipment["delivery"]["location_index"] = coord_to_index[key]

        # 6. matrices 추가
        vroom_input["matrices"] = {
            self.profile: {
                "durations": matrix_result["durations"],
                "distances": matrix_result["distances"],
            }
        }

        elapsed = int((time.time() - start_time) * 1000)
        logger.info(
            f"[MATRIX_PREP] 완료 - {len(locations)}x{len(locations)} 매트릭스, {elapsed}ms"
        )

        return vroom_input

    def _collect_unique_locations(
        self, vroom_input: Dict[str, Any],
    ) -> Tuple[List[List[float]], Dict[str, int]]:
        """
        모든 고유 좌표 수집, 등장 순서대로 인덱스 부여.

        Returns:
            (locations, coord_to_index)
            - locations: [[lon, lat], ...] 중복 없이
            - coord_to_index: {"lon,lat" → index}
        """
        locations: List[List[float]] = []
        coord_to_index: Dict[str, int] = {}

        def _add(coord: List[float]):
            key = self._coord_key(coord)
            if key not in coord_to_index:
                coord_to_index[key] = len(locations)
                locations.append(coord)

        # vehicles (start → end 순서)
        for vehicle in vroom_input.get("vehicles", []):
            if "start" in vehicle:
                _add(vehicle["start"])
            if "end" in vehicle:
                _add(vehicle["end"])

        # jobs
        for job in vroom_input.get("jobs", []):
            if "location" in job:
                _add(job["location"])

        # shipments
        for shipment in vroom_input.get("shipments", []):
            if "pickup" in shipment and "location" in shipment["pickup"]:
                _add(shipment["pickup"]["location"])
            if "delivery" in shipment and "location" in shipment["delivery"]:
                _add(shipment["delivery"]["location"])

        return locations, coord_to_index

    @staticmethod
    def _coord_key(coord: List[float]) -> str:
        """좌표를 문자열 키로 변환 (소수점 6자리)"""
        return f"{coord[0]:.6f},{coord[1]:.6f}"
