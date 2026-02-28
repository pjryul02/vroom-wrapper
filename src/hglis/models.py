"""
HGLIS 배차 입출력 모델

기준: HGLIS_배차엔진_통합명세서_v8.3
"""

from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field, field_validator

# ============================================================
# 공통 타입
# ============================================================

Grade = Literal["S", "A", "B", "C"]
TimeSlot = Literal["오전1", "오후1", "오후2", "오후3", "하루종일"]
CrewType = Literal["1인", "2인", "any"]

VALID_REGIONS = {"Y1", "Y2", "Y3", "Y5", "W1", "대전", "대구", "광주", "원주", "부산", "울산", "제주"}
METRO_REGIONS = {"Y1", "Y2", "Y3", "Y5", "W1"}
LOCAL_REGIONS = {"대전", "대구", "광주", "원주", "부산", "울산", "제주"}


def _validate_korea_coord(lon: float, lat: float, label: str = ""):
    """한국 좌표 범위 검증 (대략)"""
    if not (124 <= lon <= 132):
        raise ValueError(f"{label}경도 범위 초과: {lon} (124~132)")
    if not (33 <= lat <= 39):
        raise ValueError(f"{label}위도 범위 초과: {lat} (33~39)")


# ============================================================
# Job (오더) 관련 모델
# ============================================================

class Product(BaseModel):
    """오더 내 개별 제품"""
    model_code: str = Field(..., min_length=1, description="모델코드")
    model_name: Optional[str] = Field(None, description="모델명")
    cbm: float = Field(..., ge=0, description="CBM")
    fee: int = Field(..., ge=0, description="설치비 (원)")
    is_new_product: bool = Field(False, description="신제품 여부")
    required_grade: Grade = Field(..., description="필요 기능도 S/A/B/C")
    quantity: int = Field(1, ge=1, description="수량")
    is_sofa: bool = Field(False, description="소파 여부")


class Scheduling(BaseModel):
    """배송 스케줄링"""
    preferred_time_slot: TimeSlot = Field(..., description="희망 배송 시간대")
    service_minutes: int = Field(..., gt=0, description="설치 소요 시간 (분)")
    setup_minutes: Optional[int] = Field(None, ge=0, description="부대 작업 시간 (분)")


class JobConstraints(BaseModel):
    """오더 레벨 제약"""
    crew_type: CrewType = Field("any", description="인원 요구: 1인/2인/any")


class JobPriority(BaseModel):
    """오더 우선순위"""
    level: int = Field(0, ge=0, description="기본 우선순위")
    is_urgent: bool = Field(False, description="긴급 여부")
    is_vip: bool = Field(False, description="VIP 여부")


class Customer(BaseModel):
    """고객 정보"""
    name: Optional[str] = Field(None, description="고객명")
    phone: Optional[str] = Field(None, description="고객 연락처")
    address: Optional[str] = Field(None, description="배송 주소")


class HglisJob(BaseModel):
    """HGLIS 오더 (래퍼 입력)"""
    id: int = Field(..., gt=0, description="오더 고유 ID (양수)")
    order_id: str = Field(..., min_length=1, description="주문번호")
    location: List[float] = Field(..., min_length=2, max_length=2, description="[경도, 위도]")
    region_code: str = Field(..., description="권역코드")
    products: List[Product] = Field(..., min_length=1, description="제품 목록 (최소 1개)")
    scheduling: Scheduling
    constraints: JobConstraints = Field(default_factory=lambda: JobConstraints())
    priority: JobPriority = Field(default_factory=lambda: JobPriority())
    customer: Optional[Customer] = None

    @field_validator("location")
    @classmethod
    def validate_location(cls, v):
        _validate_korea_coord(v[0], v[1], "오더 ")
        return v

    @field_validator("region_code")
    @classmethod
    def validate_region(cls, v):
        if v not in VALID_REGIONS:
            raise ValueError(f"유효하지 않은 권역코드: {v} (허용: {VALID_REGIONS})")
        return v


# ============================================================
# Vehicle (기사) 관련 모델
# ============================================================

class VehicleLocation(BaseModel):
    """기사 출발/복귀 위치"""
    start: List[float] = Field(..., min_length=2, max_length=2, description="출발지 [경도, 위도]")
    end: List[float] = Field(..., min_length=2, max_length=2, description="복귀지 [경도, 위도]")

    @field_validator("start", "end")
    @classmethod
    def validate_coord(cls, v):
        _validate_korea_coord(v[0], v[1], "기사 ")
        return v


class Crew(BaseModel):
    """기사 팀 구성"""
    size: Literal[1, 2] = Field(..., description="인원수 (1 또는 2)")
    is_filler: bool = Field(False, description="합배차 가능 여부")


class AvoidModel(BaseModel):
    """미결 이력 모델"""
    model: str = Field(..., min_length=1, description="모델코드")
    date: Optional[str] = Field(None, description="미결 발생일")


class FeeStatus(BaseModel):
    """기사 설치비 현황"""
    monthly_accumulated: int = Field(0, ge=0, description="당월 누적 설치비 (원)")


class WorkTime(BaseModel):
    """근무 시간"""
    end: Optional[str] = Field(None, description="종료 시각 (HH:MM)")
    breaks: Optional[List[Dict[str, str]]] = Field(None, description="휴게 시간 [{start, end}]")


class HglisVehicle(BaseModel):
    """HGLIS 기사 (래퍼 입력)"""
    id: int = Field(..., gt=0, description="기사 고유 ID (양수)")
    driver_id: str = Field(..., min_length=1, description="기사ID")
    driver_name: Optional[str] = Field(None, description="기사명")
    skill_grade: Grade = Field(..., description="기능도 S/A/B/C")
    service_grade: Grade = Field(..., description="서비스등급 S/A/B/C")
    capacity_cbm: float = Field(..., gt=0, description="적재 용량 CBM")
    location: VehicleLocation
    region_code: str = Field(..., description="소속 권역코드")
    crew: Crew
    new_product_restricted: bool = Field(False, description="신제품 배정 회피 (C7, 관리자 체크)")
    avoid_models: List[AvoidModel] = Field(default_factory=list, description="미결 이력 모델 (C8)")
    fee_status: FeeStatus = Field(default_factory=lambda: FeeStatus())
    work_time: Optional[WorkTime] = None

    @field_validator("region_code")
    @classmethod
    def validate_region(cls, v):
        if v not in VALID_REGIONS:
            raise ValueError(f"유효하지 않은 권역코드: {v} (허용: {VALID_REGIONS})")
        return v


# ============================================================
# 요청/응답
# ============================================================

class DispatchMeta(BaseModel):
    """배차 요청 메타정보"""
    request_id: Optional[str] = None
    date: str = Field(..., description="배차 기준일 (YYYY-MM-DD)")
    region_mode: Literal["strict", "flexible", "ignore"] = Field(
        "strict", description="권역 매칭 모드"
    )


class DispatchOptions(BaseModel):
    """배차 옵션"""
    max_tasks_per_driver: int = Field(12, ge=1, description="기사 당 최대 건수")
    enable_joint_dispatch: bool = Field(False, description="합배차 활성화 (Phase 3)")
    geometry: bool = Field(True, description="경로 지오메트리 포함")


class HglisDispatchRequest(BaseModel):
    """POST /dispatch 요청 본문"""
    meta: DispatchMeta
    jobs: List[HglisJob] = Field(..., min_length=1, description="오더 목록")
    vehicles: List[HglisVehicle] = Field(..., min_length=1, description="기사 목록")
    options: DispatchOptions = Field(default_factory=lambda: DispatchOptions())


# --- 응답 ---

class DispatchResult(BaseModel):
    """개별 오더 배차 결과"""
    order_id: str
    dispatch_type: Literal["단독", "합배차_주", "합배차_보조"]
    driver_id: str
    driver_name: Optional[str] = None
    delivery_sequence: int
    scheduled_arrival: Optional[str] = None
    install_fee: int = 0
    geometry: Optional[Any] = None


class DriverSummary(BaseModel):
    """기사별 요약"""
    driver_id: str
    driver_name: Optional[str] = None
    skill_grade: Grade
    service_grade: Grade
    assigned_count: int = 0
    total_fee: int = 0
    distance_km: float = 0
    c2_status: Literal["ok", "warning"] = "ok"
    c2_threshold: int = 0
    monthly_after: int = 0
    c6_status: Literal["ok", "warning", "over"] = "ok"
    c6_cap: int = 0


class UnassignedJob(BaseModel):
    """미배정 오더"""
    order_id: str
    constraint: str
    reason: str


class HglisDispatchResponse(BaseModel):
    """POST /dispatch 응답"""
    status: Literal["success", "partial", "failed"]
    meta: Dict[str, Any]
    statistics: Dict[str, Any]
    results: List[DispatchResult] = []
    driver_summary: List[DriverSummary] = []
    unassigned: List[UnassignedJob] = []
    warnings: List[Dict[str, Any]] = []
