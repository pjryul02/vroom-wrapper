#!/usr/bin/env python3
"""
VROOM Wrapper v3.0 - API Request/Response Models

Pydantic 모델 기반 Swagger(OpenAPI) 문서 자동 생성용.
FastAPI 엔드포인트에서 사용하여 /docs에서 필드별 타입/설명/예시를 제공한다.
"""

from pydantic import BaseModel, ConfigDict, Field
from typing import Dict, Any, List, Optional


# ============================================================
# Request Models - 공통 컴포넌트
# ============================================================

class VehicleInput(BaseModel):
    """차량 정의"""
    model_config = ConfigDict(extra="allow")

    id: int = Field(..., description="차량 고유 ID")
    start: List[float] = Field(..., description="출발지 좌표 [경도, 위도]", min_length=2, max_length=2)
    end: Optional[List[float]] = Field(None, description="도착지 좌표 [경도, 위도] (미지정 시 출발지로 복귀)")
    capacity: Optional[List[int]] = Field(None, description="적재 용량 배열 (예: [100])")
    skills: Optional[List[int]] = Field(None, description="보유 스킬 ID 목록 (예: [1, 2])")
    time_window: Optional[List[int]] = Field(None, description="근무 시간 [시작, 종료] UNIX timestamp", min_length=2, max_length=2)
    max_tasks: Optional[int] = Field(None, description="최대 배정 작업 수")
    speed_factor: Optional[float] = Field(None, description="속도 계수 (0.1~2.0, 기본 1.0)", ge=0.1, le=2.0)
    breaks: Optional[List[Dict[str, Any]]] = Field(None, description="휴식 시간 목록")
    description: Optional[str] = Field(None, description="차량 설명")


class JobInput(BaseModel):
    """작업(배송) 정의"""
    model_config = ConfigDict(extra="allow")

    id: int = Field(..., description="작업 고유 ID")
    location: List[float] = Field(..., description="배송지 좌표 [경도, 위도]", min_length=2, max_length=2)
    service: Optional[int] = Field(300, description="현장 서비스 시간 (초, 기본 300)")
    delivery: Optional[List[int]] = Field(None, description="배송 물량 배열 (예: [10])")
    pickup: Optional[List[int]] = Field(None, description="수거 물량 배열 (예: [5])")
    skills: Optional[List[int]] = Field(None, description="필요 스킬 ID 목록 (예: [1])")
    priority: Optional[int] = Field(0, description="우선순위 (0-100, 높을수록 우선)", ge=0, le=100)
    time_windows: Optional[List[List[int]]] = Field(None, description="배송 가능 시간대 [[시작, 종료], ...] UNIX timestamp")
    description: Optional[str] = Field(None, description="작업 설명 ('VIP customer' 등 비즈니스 규칙 트리거)")


class ShipmentInput(BaseModel):
    """수거+배송 쌍 (Pickup & Delivery)"""
    model_config = ConfigDict(extra="allow")

    id: int = Field(..., description="쉽먼트 고유 ID")
    pickup: Dict[str, Any] = Field(..., description="수거 정보 {location: [경도, 위도], service: 초, ...}")
    delivery: Dict[str, Any] = Field(..., description="배송 정보 {location: [경도, 위도], service: 초, ...}")
    amount: List[int] = Field(..., description="운송 물량 배열 (예: [10])")
    skills: Optional[List[int]] = Field(None, description="필요 스킬 ID 목록")
    priority: Optional[int] = Field(0, description="우선순위 (0-100)", ge=0, le=100)


class VROOMOptions(BaseModel):
    """VROOM 엔진 옵션"""
    model_config = ConfigDict(extra="allow")

    g: Optional[bool] = Field(False, description="true면 경로 geometry(polyline) 포함")


class BusinessRulesInput(BaseModel):
    """비즈니스 규칙 설정 (래퍼 전용)"""
    model_config = ConfigDict(extra="allow")

    vip_job_ids: Optional[List[int]] = Field(None, description="VIP 작업 ID 목록 (우선 배정)")
    urgent_job_ids: Optional[List[int]] = Field(None, description="긴급 작업 ID 목록")
    enable_vip: Optional[bool] = Field(True, description="VIP 규칙 활성화 (자동 탐지)")
    enable_urgent: Optional[bool] = Field(True, description="긴급 규칙 활성화 (자동 탐지)")
    enable_region_constraints: Optional[bool] = Field(False, description="지역 제약 활성화")
    enable_time_priority: Optional[bool] = Field(False, description="시간대별 우선순위 활성화")
    region_assignment: Optional[Dict[str, List[int]]] = Field(
        None, description='지역별 차량 할당 {"seoul": [1,2], "busan": [3]}'
    )


# ============================================================
# Request Models - 엔드포인트별
# ============================================================

class DistributeRequest(BaseModel):
    """
    VROOM 호환 배차 요청

    VROOM 표준 JSON 포맷 그대로 전송. API Key 불필요.
    Route Playground 및 외부 VROOM 호환 도구에서 사용.
    """
    model_config = ConfigDict(
        extra="allow",
        json_schema_extra={
            "example": {
                "vehicles": [
                    {
                        "id": 1,
                        "start": [127.0276, 37.4979],
                        "end": [127.0276, 37.4979],
                        "capacity": [100],
                        "time_window": [1700000000, 1700036000]
                    },
                    {
                        "id": 2,
                        "start": [126.9780, 37.5665],
                        "end": [126.9780, 37.5665],
                        "capacity": [100],
                        "time_window": [1700000000, 1700036000]
                    }
                ],
                "jobs": [
                    {"id": 1, "location": [127.0500, 37.5172], "service": 300, "delivery": [10]},
                    {"id": 2, "location": [127.0300, 37.4850], "service": 300, "delivery": [15]},
                    {"id": 3, "location": [126.9700, 37.5550], "service": 300, "delivery": [20]}
                ],
                "options": {"g": True}
            }
        }
    )

    vehicles: List[VehicleInput] = Field(..., description="차량 목록 (1개 이상 필수)", min_length=1)
    jobs: Optional[List[JobInput]] = Field(default=[], description="작업(배송) 목록")
    shipments: Optional[List[ShipmentInput]] = Field(default=[], description="수거+배송 쌍 목록")
    options: Optional[VROOMOptions] = Field(None, description="VROOM 엔진 옵션")


class OptimizeRequest(BaseModel):
    """
    VROOM Wrapper 최적화 요청

    VROOM 포맷 + 래퍼 전용 필드 (use_cache, business_rules).
    API Key 필수 (Header: X-API-Key).
    """
    model_config = ConfigDict(
        extra="allow",
        json_schema_extra={
            "example": {
                "vehicles": [
                    {
                        "id": 1,
                        "start": [127.0276, 37.4979],
                        "end": [127.0276, 37.4979],
                        "capacity": [100],
                        "time_window": [1700000000, 1700036000]
                    },
                    {
                        "id": 2,
                        "start": [126.9780, 37.5665],
                        "end": [126.9780, 37.5665],
                        "capacity": [100],
                        "time_window": [1700000000, 1700036000]
                    }
                ],
                "jobs": [
                    {"id": 1, "location": [127.0500, 37.5172], "service": 300, "delivery": [10], "description": "VIP customer"},
                    {"id": 2, "location": [127.0300, 37.4850], "service": 300, "delivery": [15]},
                    {"id": 3, "location": [126.9700, 37.5550], "service": 300, "delivery": [20]}
                ],
                "use_cache": False,
                "business_rules": {
                    "vip_job_ids": [1]
                }
            }
        }
    )

    vehicles: List[VehicleInput] = Field(..., description="차량 목록 (1개 이상 필수)", min_length=1)
    jobs: Optional[List[JobInput]] = Field(default=[], description="작업(배송) 목록")
    shipments: Optional[List[ShipmentInput]] = Field(default=[], description="수거+배송 쌍 목록")
    options: Optional[VROOMOptions] = Field(None, description="VROOM 엔진 옵션")
    use_cache: Optional[bool] = Field(True, description="캐시 사용 여부 (기본 true)")
    business_rules: Optional[BusinessRulesInput] = Field(None, description="비즈니스 규칙 설정 (VIP/긴급/지역)")


class MatrixBuildRequest(BaseModel):
    """
    대규모 매트릭스 생성 요청

    OSRM 서버에서 거리/시간 매트릭스를 청킹 방식으로 생성.
    250개 이상 좌표에서 유용.
    """
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "locations": [
                    [127.0276, 37.4979],
                    [127.0500, 37.5172],
                    [126.9250, 37.5260],
                    [127.0300, 37.4850]
                ],
                "profile": "driving"
            }
        }
    )

    locations: List[List[float]] = Field(..., description="좌표 목록 [[경도, 위도], ...]", min_length=2)
    profile: Optional[str] = Field("driving", description="라우팅 프로필 (driving)")
