"""
GPS 좌표 기하 계산 유틸리티
"""

import math
from typing import Tuple


def haversine_distance(coord1: Tuple[float, float], coord2: Tuple[float, float]) -> float:
    """
    두 좌표 간의 haversine 거리 계산 (미터)

    Args:
        coord1: (위도, 경도) 튜플
        coord2: (위도, 경도) 튜플

    Returns:
        float: 두 좌표 간의 거리 (미터)
    """
    lat1, lon1 = math.radians(coord1[0]), math.radians(coord1[1])
    lat2, lon2 = math.radians(coord2[0]), math.radians(coord2[1])

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))

    return 6371000 * c


def calculate_bearing(coord1: Tuple[float, float], coord2: Tuple[float, float]) -> float:
    """
    두 좌표 간의 방향각 계산 (도)

    Args:
        coord1: (위도, 경도)
        coord2: (위도, 경도)

    Returns:
        float: 방향각 (0-360도)
    """
    lat1, lon1 = math.radians(coord1[0]), math.radians(coord1[1])
    lat2, lon2 = math.radians(coord2[0]), math.radians(coord2[1])

    dlon = lon2 - lon1

    y = math.sin(dlon) * math.cos(lat2)
    x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)

    bearing = math.atan2(y, x)
    bearing = math.degrees(bearing)
    bearing = (bearing + 360) % 360

    return bearing


def calculate_speed(point1: Tuple[float, float, float],
                   point2: Tuple[float, float, float]) -> float:
    """
    두 GPS 포인트 간의 속도 계산 (m/s)

    Args:
        point1: (경도, 위도, 시간)
        point2: (경도, 위도, 시간)
    """
    if len(point1) < 3 or len(point2) < 3:
        return 0.0

    distance = haversine_distance((point1[1], point1[0]), (point2[1], point2[0]))
    time_diff = abs(point2[2] - point1[2])

    if time_diff > 0:
        return distance / time_diff
    return 0.0


def calculate_acceleration(point1: Tuple[float, float, float],
                          point2: Tuple[float, float, float],
                          point3: Tuple[float, float, float]) -> float:
    """세 GPS 포인트로부터 가속도 계산 (m/s²)"""
    speed1 = calculate_speed(point1, point2)
    speed2 = calculate_speed(point2, point3)

    time_diff = point3[2] - point1[2]

    if time_diff > 0:
        return (speed2 - speed1) / (time_diff / 2.0)
    return 0.0


def normalize_angle(angle: float) -> float:
    """각도를 0-360 범위로 정규화"""
    return angle % 360


def angle_difference(angle1: float, angle2: float) -> float:
    """두 각도 간의 최소 차이 계산 (0-180도)"""
    diff = abs(angle1 - angle2)
    if diff > 180:
        diff = 360 - diff
    return diff
