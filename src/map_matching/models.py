"""
맵 매칭 Pydantic 모델
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator


class MapMatchingRequest(BaseModel):
    """맵 매칭 요청 모델"""
    trajectory: List[List[float]] = Field(
        ...,
        description="GPS 궤적 [[경도, 위도, 타임스탬프, 정확도, 속도], ...]",
        min_length=2,
    )
    enable_debug: bool = Field(
        False,
        description="디버그 정보 활성화"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "trajectory": [
                    [126.9780, 37.5665, 1734068400, 5.0, 0.0],
                    [126.9820, 37.5670, 1734068460, 8.0, 12.5],
                    [126.9850, 37.5675, 1734068520, 6.0, 15.0],
                    [126.9890, 37.5680, 1734068580, 10.0, 18.0],
                    [126.9920, 37.5685, 1734068640, 7.0, 14.0],
                    [126.9950, 37.5690, 1734068700, 5.0, 16.0]
                ]
            }
        }
    }

    @field_validator('trajectory')
    @classmethod
    def validate_trajectory(cls, v):
        if len(v) < 2:
            raise ValueError('최소 2개 이상의 GPS 포인트가 필요합니다')

        for i, point in enumerate(v):
            if len(point) != 5:
                raise ValueError(
                    f'포인트 {i}: [경도, 위도, 타임스탬프, 정확도, 속도] 5개 값이 필요합니다. '
                    f'현재 {len(point)}개 값 제공됨'
                )

            lon, lat, timestamp, accuracy, speed = point

            if not isinstance(lon, (int, float)) or not -180 <= lon <= 180:
                raise ValueError(f'포인트 {i}: 경도({lon})는 -180 ~ 180 범위여야 합니다')
            if not isinstance(lat, (int, float)) or not -90 <= lat <= 90:
                raise ValueError(f'포인트 {i}: 위도({lat})는 -90 ~ 90 범위여야 합니다')
            if not isinstance(timestamp, (int, float)) or timestamp < 0:
                raise ValueError(f'포인트 {i}: 타임스탬프({timestamp})는 0 이상이어야 합니다')
            if not isinstance(accuracy, (int, float)) or accuracy < 0:
                raise ValueError(f'포인트 {i}: 정확도({accuracy})는 0 이상이어야 합니다')
            if not isinstance(speed, (int, float)) or speed < 0:
                raise ValueError(f'포인트 {i}: 속도({speed})는 0 이상이어야 합니다')

        return v


class MapMatchingSummary(BaseModel):
    """맵 매칭 결과 요약"""
    total_points: int
    matched_points: int


class MapMatchingResponse(BaseModel):
    """맵 매칭 응답 모델"""
    matched_trace: List[List[float]] = Field(
        ...,
        description="매칭된 궤적 [[경도, 위도, 타임스탬프, 플래그], ...]"
    )
    summary: MapMatchingSummary
    debug_info: Optional[Dict[str, Any]] = None


class StandardResponse(BaseModel):
    """표준 응답 모델"""
    status: str
    message: str
    data: Optional[MapMatchingResponse] = None
