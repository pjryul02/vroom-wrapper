"""
OSRM API 파라미터 빌더
"""

from typing import List
from .geometry import calculate_bearing
from .config import (
    DEFAULT_GPS_ACCURACY,
    MIN_MATCHING_RADIUS,
    BEARING_RANGE,
    SPEED_LOW_THRESHOLD,
    SPEED_HIGH_THRESHOLD,
    RADIUS_FACTOR_LOW_SPEED,
    RADIUS_FACTOR_MID_SPEED,
    RADIUS_FACTOR_HIGH_SPEED,
)


class OSRMParameterBuilder:
    """OSRM Match API 파라미터 빌더"""

    def build_coordinates(self, trajectory: List[List[float]]) -> str:
        coordinates = [f"{point[0]},{point[1]}" for point in trajectory]
        return ";".join(coordinates)

    def build_timestamps(self, trajectory: List[List[float]]) -> str:
        timestamps = [str(int(point[2])) for point in trajectory]
        return ";".join(timestamps)

    def build_radiuses(self, trajectory: List[List[float]]) -> str:
        radiuses = []
        for point in trajectory:
            accuracy = point[3] if len(point) > 3 else DEFAULT_GPS_ACCURACY
            speed = point[4] if len(point) > 4 else 0

            if speed > SPEED_HIGH_THRESHOLD:
                speed_factor = RADIUS_FACTOR_HIGH_SPEED
            elif speed > SPEED_LOW_THRESHOLD:
                speed_factor = RADIUS_FACTOR_MID_SPEED
            else:
                speed_factor = RADIUS_FACTOR_LOW_SPEED

            radius = max(accuracy * speed_factor, MIN_MATCHING_RADIUS)
            radiuses.append(str(int(radius)))

        return ";".join(radiuses)

    def build_bearings(self, trajectory: List[List[float]]) -> str:
        if len(trajectory) < 2:
            return ""

        bearings = []
        for i, point in enumerate(trajectory):
            if i == 0:
                bearing = calculate_bearing(
                    (point[1], point[0]),
                    (trajectory[i+1][1], trajectory[i+1][0])
                )
            elif i == len(trajectory) - 1:
                bearing = calculate_bearing(
                    (trajectory[i-1][1], trajectory[i-1][0]),
                    (point[1], point[0])
                )
            else:
                bearing_from_prev = calculate_bearing(
                    (trajectory[i-1][1], trajectory[i-1][0]),
                    (point[1], point[0])
                )
                bearing_to_next = calculate_bearing(
                    (point[1], point[0]),
                    (trajectory[i+1][1], trajectory[i+1][0])
                )
                bearing = (bearing_from_prev + bearing_to_next) / 2

            bearings.append(f"{int(bearing)},{BEARING_RANGE}")

        return ";".join(bearings)

    def build_match_params(
        self,
        trajectory: List[List[float]],
        include_steps: bool = False,
        include_geometry: bool = True,
        include_annotations: bool = True,
        tidy: bool = True
    ) -> dict:
        params = {
            'timestamps': self.build_timestamps(trajectory),
            'radiuses': self.build_radiuses(trajectory),
            'bearings': self.build_bearings(trajectory),
            'steps': 'true' if include_steps else 'false',
            'geometries': 'geojson' if include_geometry else 'polyline',
            'annotations': 'true' if include_annotations else 'false',
        }

        if tidy:
            params['tidy'] = 'true'

        return params
