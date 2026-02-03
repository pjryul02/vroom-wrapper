#!/usr/bin/env python3
"""
InputValidator - Pydantic 기반 입력 검증

Phase 1.2.1: 입력 데이터 검증 및 타입 강제
"""

from pydantic import BaseModel, Field, validator, root_validator
from typing import List, Optional, Dict, Any
from enum import Enum


class Location:
    """좌표 검증 유틸리티"""

    @staticmethod
    def from_list(coords: List[float]) -> tuple:
        """좌표 리스트 검증 및 파싱"""
        if len(coords) != 2:
            raise ValueError(f"Location must be [lon, lat], got {len(coords)} elements")

        lon, lat = coords

        # 경도 범위: -180 ~ 180
        if not (-180 <= lon <= 180):
            raise ValueError(f"Longitude {lon} out of range [-180, 180]")

        # 위도 범위: -90 ~ 90
        if not (-90 <= lat <= 90):
            raise ValueError(f"Latitude {lat} out of range [-90, 90]")

        return (lon, lat)


class TimeWindow:
    """시간창 검증 유틸리티"""

    def __init__(self, start: int, end: int):
        if start < 0:
            raise ValueError(f"Time window start must be >= 0, got {start}")
        if end < start:
            raise ValueError(f"Time window end ({end}) must be >= start ({start})")

        self.start = start
        self.end = end


class Break(BaseModel):
    """휴게 시간 모델"""
    id: str
    time_windows: List[List[int]]
    service: int = Field(default=300, ge=0)  # 기본 5분
    description: Optional[str] = None

    @validator('time_windows')
    def validate_time_windows(cls, v):
        """시간창 검증"""
        if not v:
            raise ValueError("Break must have at least one time window")

        for tw in v:
            if len(tw) != 2:
                raise ValueError(f"Time window must be [start, end], got {tw}")
            TimeWindow(start=tw[0], end=tw[1])  # 검증

        return v


class Vehicle(BaseModel):
    """차량 모델"""
    id: int
    start: List[float]  # [lon, lat]
    end: Optional[List[float]] = None
    capacity: Optional[List[int]] = Field(default=[1000])
    skills: Optional[List[int]] = Field(default=[])
    time_window: Optional[List[int]] = None
    max_tasks: Optional[int] = None
    breaks: Optional[List[Break]] = Field(default=[])
    speed_factor: Optional[float] = Field(default=1.0, ge=0.1, le=2.0)
    description: Optional[str] = None

    @validator('start', 'end')
    def validate_location(cls, v):
        """좌표 검증"""
        if v:
            Location.from_list(v)  # 검증
        return v

    @validator('end')
    def end_default_to_start(cls, v, values):
        """end 미지정 시 start로 복귀"""
        return v if v else values.get('start')

    @validator('time_window')
    def validate_time_window(cls, v):
        """차량 시간창 검증"""
        if v:
            if len(v) != 2:
                raise ValueError(f"Vehicle time_window must be [start, end], got {v}")
            TimeWindow(start=v[0], end=v[1])
        return v

    @validator('capacity')
    def validate_capacity(cls, v):
        """용량 검증"""
        if v:
            for cap in v:
                if cap < 0:
                    raise ValueError(f"Capacity must be >= 0, got {cap}")
        return v

    @validator('max_tasks')
    def validate_max_tasks(cls, v):
        """최대 작업 수 검증"""
        if v is not None and v < 1:
            raise ValueError(f"max_tasks must be >= 1, got {v}")
        return v


class Job(BaseModel):
    """작업 모델"""
    id: int
    location: List[float]  # [lon, lat]
    service: int = Field(default=300, ge=0)  # 기본 5분
    delivery: Optional[List[int]] = None
    pickup: Optional[List[int]] = None
    skills: Optional[List[int]] = Field(default=[])
    priority: int = Field(default=0, ge=0, le=100)
    time_windows: Optional[List[List[int]]] = None
    description: Optional[str] = None

    @validator('location')
    def validate_location(cls, v):
        """좌표 검증"""
        if len(v) != 2:
            raise ValueError(f"Location must be [lon, lat], got {len(v)} elements")
        Location.from_list(v)
        return v

    @validator('time_windows')
    def validate_time_windows(cls, v):
        """시간창 검증"""
        if v:
            for tw in v:
                if len(tw) != 2:
                    raise ValueError(f"Time window must be [start, end], got {tw}")
                TimeWindow(start=tw[0], end=tw[1])
        return v

    @validator('delivery', 'pickup')
    def validate_amounts(cls, v):
        """배송/픽업 수량 검증"""
        if v:
            for amount in v:
                if amount < 0:
                    raise ValueError(f"Amount must be >= 0, got {amount}")
        return v


class Shipment(BaseModel):
    """배송 쌍 (pickup + delivery)"""
    id: int
    pickup: Dict[str, Any]  # Job 형태
    delivery: Dict[str, Any]  # Job 형태
    amount: List[int]
    skills: Optional[List[int]] = Field(default=[])
    priority: int = Field(default=0, ge=0, le=100)

    @validator('pickup', 'delivery')
    def validate_job_location(cls, v):
        """pickup/delivery의 location 검증"""
        if 'location' not in v:
            raise ValueError("pickup/delivery must have 'location' field")

        location = v['location']
        if len(location) != 2:
            raise ValueError(f"Location must be [lon, lat], got {len(location)} elements")

        Location.from_list(location)
        return v

    @validator('amount')
    def validate_amount(cls, v):
        """수량 검증"""
        if not v:
            raise ValueError("Shipment must have at least one amount")

        for amount in v:
            if amount <= 0:
                raise ValueError(f"Shipment amount must be > 0, got {amount}")

        return v


class VRPInput(BaseModel):
    """전체 VRP 입력 검증"""
    vehicles: List[Vehicle]
    jobs: Optional[List[Job]] = Field(default=[])
    shipments: Optional[List[Shipment]] = Field(default=[])

    @validator('vehicles')
    def at_least_one_vehicle(cls, v):
        """최소 1개 차량 필요"""
        if not v:
            raise ValueError("At least one vehicle required")
        return v

    @root_validator(skip_on_failure=True)
    def jobs_or_shipments_required(cls, values):
        """jobs 또는 shipments 중 하나는 필수"""
        jobs = values.get('jobs', [])
        shipments = values.get('shipments', [])

        if not jobs and not shipments:
            raise ValueError("Either jobs or shipments required")

        return values

    @root_validator(skip_on_failure=True)
    def validate_unique_ids(cls, values):
        """ID 중복 검증"""
        # 차량 ID 중복 체크
        vehicles = values.get('vehicles', [])
        vehicle_ids = [v.id for v in vehicles]
        if len(vehicle_ids) != len(set(vehicle_ids)):
            raise ValueError(f"Duplicate vehicle IDs found: {vehicle_ids}")

        # Job ID 중복 체크
        jobs = values.get('jobs', [])
        job_ids = [j.id for j in jobs]
        if len(job_ids) != len(set(job_ids)):
            raise ValueError(f"Duplicate job IDs found: {job_ids}")

        # Shipment ID 중복 체크
        shipments = values.get('shipments', [])
        shipment_ids = [s.id for s in shipments]
        if len(shipment_ids) != len(set(shipment_ids)):
            raise ValueError(f"Duplicate shipment IDs found: {shipment_ids}")

        return values

    class Config:
        # 추가 필드 허용 (VROOM의 확장 필드)
        extra = "allow"


class InputValidator:
    """입력 검증 메인 클래스"""

    @staticmethod
    def validate(data: Dict[str, Any]) -> VRPInput:
        """
        입력 데이터 검증

        Args:
            data: 원본 VRP 입력 딕셔너리

        Returns:
            VRPInput: 검증된 Pydantic 모델

        Raises:
            ValueError: 검증 실패 시
        """
        try:
            vrp_input = VRPInput(**data)
            return vrp_input
        except Exception as e:
            raise ValueError(f"Input validation failed: {str(e)}")

    @staticmethod
    def validate_and_dict(data: Dict[str, Any]) -> Dict[str, Any]:
        """
        검증 후 딕셔너리로 반환

        Args:
            data: 원본 VRP 입력 딕셔너리

        Returns:
            Dict: 검증된 데이터 딕셔너리
        """
        vrp_input = InputValidator.validate(data)
        return vrp_input.dict(exclude_none=True)
