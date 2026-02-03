#!/usr/bin/env python3
"""
InputNormalizer - 입력 데이터 정규화

Phase 1.2.2: 좌표계 변환, 시간 정규화, 기본값 처리
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class InputNormalizer:
    """입력 데이터 정규화"""

    def __init__(self):
        self.default_service_time = 300  # 5분
        self.default_capacity = [1000]
        self.default_speed_factor = 1.0

    def normalize(self, vrp_input: Dict[str, Any]) -> Dict[str, Any]:
        """
        입력 데이터 정규화

        Args:
            vrp_input: 원본 VRP 입력

        Returns:
            정규화된 VRP 입력
        """
        normalized = vrp_input.copy()

        # 1. 차량 정규화
        if 'vehicles' in normalized:
            normalized['vehicles'] = [
                self._normalize_vehicle(v) for v in normalized['vehicles']
            ]

        # 2. 작업 정규화
        if 'jobs' in normalized:
            normalized['jobs'] = [
                self._normalize_job(j) for j in normalized['jobs']
            ]

        # 3. Shipment 정규화
        if 'shipments' in normalized:
            normalized['shipments'] = [
                self._normalize_shipment(s) for s in normalized['shipments']
            ]

        # 4. 시간 기준 정규화 (옵션)
        if 'time_base' in normalized:
            normalized = self._normalize_time_base(normalized)

        return normalized

    def _normalize_vehicle(self, vehicle: Dict[str, Any]) -> Dict[str, Any]:
        """
        차량 정규화

        - end 미지정 시 start로 설정 (차량 복귀)
        - capacity 기본값
        - speed_factor 기본값
        - skills 기본값
        """
        normalized = vehicle.copy()

        # end 미지정 시 start로 복귀
        if 'end' not in normalized or normalized['end'] is None:
            normalized['end'] = normalized['start']

        # capacity 기본값
        if 'capacity' not in normalized:
            normalized['capacity'] = self.default_capacity.copy()

        # speed_factor 기본값
        if 'speed_factor' not in normalized:
            normalized['speed_factor'] = self.default_speed_factor

        # skills 기본값
        if 'skills' not in normalized:
            normalized['skills'] = []

        # breaks 기본값
        if 'breaks' not in normalized:
            normalized['breaks'] = []

        return normalized

    def _normalize_job(self, job: Dict[str, Any]) -> Dict[str, Any]:
        """
        작업 정규화

        - service 기본값
        - skills 기본값
        - priority 기본값
        - delivery/pickup 기본값
        """
        normalized = job.copy()

        # service 기본값
        if 'service' not in normalized:
            normalized['service'] = self.default_service_time

        # skills 기본값
        if 'skills' not in normalized:
            normalized['skills'] = []

        # priority 기본값
        if 'priority' not in normalized:
            normalized['priority'] = 0

        # delivery/pickup 기본값
        if 'delivery' not in normalized and 'pickup' not in normalized:
            # 아무것도 없으면 delivery [1] 기본값
            normalized['delivery'] = [1]

        return normalized

    def _normalize_shipment(self, shipment: Dict[str, Any]) -> Dict[str, Any]:
        """
        Shipment 정규화

        - pickup/delivery의 service 기본값
        - skills 기본값
        - priority 기본값
        """
        normalized = shipment.copy()

        # pickup 정규화
        if 'pickup' in normalized:
            pickup = normalized['pickup'].copy()
            if 'service' not in pickup:
                pickup['service'] = self.default_service_time
            normalized['pickup'] = pickup

        # delivery 정규화
        if 'delivery' in normalized:
            delivery = normalized['delivery'].copy()
            if 'service' not in delivery:
                delivery['service'] = self.default_service_time
            normalized['delivery'] = delivery

        # skills 기본값
        if 'skills' not in normalized:
            normalized['skills'] = []

        # priority 기본값
        if 'priority' not in normalized:
            normalized['priority'] = 0

        return normalized

    def _normalize_time_base(self, vrp_input: Dict[str, Any]) -> Dict[str, Any]:
        """
        시간 기준 정규화

        사용자가 절대 시간(ISO 8601)으로 입력한 경우
        VROOM의 상대 시간(초 단위)으로 변환

        예:
        {
            "time_base": "2026-01-24T09:00:00",
            "vehicles": [{
                "time_window": ["2026-01-24T09:00:00", "2026-01-24T18:00:00"]
            }],
            "jobs": [{
                "time_windows": [["2026-01-24T10:00:00", "2026-01-24T12:00:00"]]
            }]
        }

        →

        {
            "vehicles": [{
                "time_window": [0, 32400]  # 9시간 = 32400초
            }],
            "jobs": [{
                "time_windows": [[3600, 10800]]  # 1-3시간
            }]
        }
        """
        time_base_str = vrp_input.get('time_base')
        if not time_base_str:
            return vrp_input

        try:
            time_base = datetime.fromisoformat(time_base_str)
        except ValueError as e:
            logger.warning(f"Invalid time_base format: {time_base_str}, ignoring")
            return vrp_input

        normalized = vrp_input.copy()

        # 차량 시간창 변환
        if 'vehicles' in normalized:
            for vehicle in normalized['vehicles']:
                if 'time_window' in vehicle:
                    vehicle['time_window'] = self._convert_time_window(
                        vehicle['time_window'],
                        time_base
                    )

        # 작업 시간창 변환
        if 'jobs' in normalized:
            for job in normalized['jobs']:
                if 'time_windows' in job:
                    job['time_windows'] = [
                        self._convert_time_window(tw, time_base)
                        for tw in job['time_windows']
                    ]

        # Shipment 시간창 변환
        if 'shipments' in normalized:
            for shipment in normalized['shipments']:
                if 'pickup' in shipment and 'time_windows' in shipment['pickup']:
                    shipment['pickup']['time_windows'] = [
                        self._convert_time_window(tw, time_base)
                        for tw in shipment['pickup']['time_windows']
                    ]
                if 'delivery' in shipment and 'time_windows' in shipment['delivery']:
                    shipment['delivery']['time_windows'] = [
                        self._convert_time_window(tw, time_base)
                        for tw in shipment['delivery']['time_windows']
                    ]

        # time_base 제거 (VROOM에 전달하지 않음)
        del normalized['time_base']

        logger.info(f"Normalized time_base: {time_base_str}")

        return normalized

    def _convert_time_window(
        self,
        time_window: List,
        time_base: datetime
    ) -> List[int]:
        """
        시간창을 절대 시간에서 상대 시간(초)으로 변환

        Args:
            time_window: [start, end] (ISO 8601 문자열 또는 초)
            time_base: 기준 시간

        Returns:
            [start_seconds, end_seconds]
        """
        if not time_window or len(time_window) != 2:
            return time_window

        start, end = time_window

        # 이미 숫자(초)인 경우 그대로 반환
        if isinstance(start, (int, float)) and isinstance(end, (int, float)):
            return [int(start), int(end)]

        # ISO 8601 문자열인 경우 변환
        try:
            start_dt = datetime.fromisoformat(start)
            end_dt = datetime.fromisoformat(end)

            start_seconds = int((start_dt - time_base).total_seconds())
            end_seconds = int((end_dt - time_base).total_seconds())

            return [start_seconds, end_seconds]
        except (ValueError, AttributeError):
            logger.warning(f"Failed to convert time_window: {time_window}")
            return time_window

    def normalize_coordinates(
        self,
        vrp_input: Dict[str, Any],
        from_crs: str = "EPSG:4326",
        to_crs: str = "EPSG:4326"
    ) -> Dict[str, Any]:
        """
        좌표계 변환

        기본적으로 WGS84(EPSG:4326)를 사용하지만,
        필요시 다른 좌표계로 변환 가능

        Args:
            vrp_input: VRP 입력
            from_crs: 원본 좌표계
            to_crs: 목표 좌표계

        Returns:
            변환된 VRP 입력

        Note:
            실제 좌표계 변환은 pyproj 또는 GDAL 라이브러리 필요
            현재는 placeholder
        """
        if from_crs == to_crs:
            return vrp_input

        # TODO: pyproj를 사용한 실제 좌표계 변환 구현
        logger.warning(
            f"Coordinate transformation not implemented: {from_crs} -> {to_crs}"
        )

        return vrp_input

    def round_coordinates(
        self,
        vrp_input: Dict[str, Any],
        precision: int = 6
    ) -> Dict[str, Any]:
        """
        좌표 반올림 (부동소수점 정밀도 제어)

        Args:
            vrp_input: VRP 입력
            precision: 소수점 자릿수 (기본 6자리 = 약 0.11m 정밀도)

        Returns:
            반올림된 VRP 입력
        """
        normalized = vrp_input.copy()

        # 차량 좌표 반올림
        if 'vehicles' in normalized:
            for vehicle in normalized['vehicles']:
                if 'start' in vehicle:
                    vehicle['start'] = [
                        round(coord, precision) for coord in vehicle['start']
                    ]
                if 'end' in vehicle:
                    vehicle['end'] = [
                        round(coord, precision) for coord in vehicle['end']
                    ]

        # 작업 좌표 반올림
        if 'jobs' in normalized:
            for job in normalized['jobs']:
                if 'location' in job:
                    job['location'] = [
                        round(coord, precision) for coord in job['location']
                    ]

        # Shipment 좌표 반올림
        if 'shipments' in normalized:
            for shipment in normalized['shipments']:
                if 'pickup' in shipment and 'location' in shipment['pickup']:
                    shipment['pickup']['location'] = [
                        round(coord, precision)
                        for coord in shipment['pickup']['location']
                    ]
                if 'delivery' in shipment and 'location' in shipment['delivery']:
                    shipment['delivery']['location'] = [
                        round(coord, precision)
                        for coord in shipment['delivery']['location']
                    ]

        return normalized
