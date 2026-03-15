"""
HGLIS 배차 입출력 모델

기준: HGLIS_배차엔진_통합명세서_v8.3
"""

from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator

# ============================================================
# 공통 타입
# ============================================================

Grade = Literal["S", "A", "B", "C", "D"]
TimeSlot = Literal["오전1", "오후1", "오후2", "오후3", "하루종일", "시간미정"]
CrewType = Literal["1인", "2인", "1인팀", "2인팀", "any"]

VALID_REGIONS = {"Y1", "Y2", "Y3", "Y5", "W1", "대전", "대구", "광주", "원주", "부산", "울산", "제주", "KP", "YN"}
METRO_REGIONS = {"Y1", "Y2", "Y3", "Y5", "W1", "KP", "YN"}
LOCAL_REGIONS = {"대전", "대구", "광주", "원주", "부산", "울산", "제주"}

# C6 월상한 (서비스등급 기준, 원)
MONTHLY_CAP: Dict[str, int] = {
    "S": 12_000_000,
    "A": 11_000_000,
    "B": 9_000_000,
    "C": 7_000_000,
}


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
    model_config = ConfigDict(protected_namespaces=())

    model_code: str = Field(..., min_length=1, description="모델코드")
    model_name: Optional[str] = Field(None, description="모델명")
    cbm: float = Field(..., ge=0, description="CBM")
    fee: int = Field(..., ge=0, description="설치비 (원)")
    is_new_product: bool = Field(False, description="신제품 여부")  # 없으면 False로 처리
    required_grade: Grade = Field(..., description="필요 기능도 S/A/B/C")
    quantity: int = Field(1, ge=1, description="수량")
    is_sofa: bool = Field(False, description="소파 여부")

    @property
    def display_name(self) -> str:
        """model_name이 없으면 model_code로 대체"""
        return self.model_name or self.model_code


class Scheduling(BaseModel):
    """배송 스케줄링"""
    preferred_time_slot: TimeSlot = Field(..., description="희망 배송 시간대")
    preferred_date: Optional[str] = Field(None, description="희망 배송일 (YYYY-MM-DD)")
    service_minutes: int = Field(..., ge=0, description="설치 소요 시간 (분, 0=서비스시간 없음)")
    setup_minutes: Optional[int] = Field(None, ge=0, description="부대 작업 시간 (분)")


class JobConstraints(BaseModel):
    """오더 레벨 제약"""
    crew_type: CrewType = Field("any", description="인원 요구: 1인/2인/any")
    required_grade: Optional[Grade] = Field(None, description="필요 기능도 (constraints 레벨)")
    is_filler_required: Optional[bool] = Field(None, description="충원기사 필요 여부")


class JobFees(BaseModel):
    """오더 수수료"""
    install_fee: int = Field(0, ge=0, description="설치비 (원)")
    product_sales_amount: Optional[int] = Field(None, ge=0, description="제품 판매액 (원)")


class JobPriority(BaseModel):
    """오더 우선순위"""
    level: int = Field(0, ge=0, description="기본 우선순위")
    is_urgent: bool = Field(False, description="긴급 여부")
    is_vip: bool = Field(False, description="VIP 여부")


class Customer(BaseModel):
    """고객 정보"""
    model_config = ConfigDict(extra="allow")
    id: Optional[str] = Field(None, description="고객 ID")
    name: Optional[str] = Field(None, description="고객명")
    phone: Optional[str] = Field(None, description="고객 연락처")
    address: Optional[str] = Field(None, description="배송 주소")
    zip: Optional[str] = Field(None, description="우편번호")


class HglisJob(BaseModel):
    """HGLIS 오더 (래퍼 입력)"""
    model_config = ConfigDict(extra="allow")
    id: int = Field(..., description="오더 고유 ID")
    order_id: str = Field(..., min_length=1, description="주문번호")
    order_type: Optional[str] = Field(None, description="주문유형 (정품/반품/회수 등)")
    location: List[float] = Field(..., min_length=2, max_length=2, description="[경도, 위도]")
    region_code: str = Field(..., description="권역코드")
    products: List[Product] = Field(default_factory=list, description="제품 목록 (빈 배열 허용)")
    scheduling: Scheduling
    constraints: JobConstraints = Field(default_factory=lambda: JobConstraints())
    priority: JobPriority = Field(default_factory=lambda: JobPriority())
    customer: Optional[Customer] = None
    fees: Optional[JobFees] = None
    order_channel: Optional[str] = Field(None, description="주문 채널")
    address_type: Optional[str] = Field(None, description="주소 유형")

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

    @property
    def computed_model_name(self) -> str:
        """products 기반 모델명 계산 (model_name null이면 model_code 사용)"""
        if not self.products:
            return self.order_id
        parts = []
        for p in self.products:
            name = p.model_name or p.model_code
            parts.append(f"{name} x{p.quantity}" if p.quantity > 1 else name)
        if len(parts) == 1:
            return parts[0]
        return f"{parts[0]} 외 {len(parts)-1}건"


# ============================================================
# Vehicle (기사) 관련 모델
# ============================================================

class VehicleLocation(BaseModel):
    """기사 출발/복귀 위치"""
    start: List[float] = Field(..., min_length=2, max_length=2, description="출발지 [경도, 위도]")
    end: List[float] = Field(..., min_length=2, max_length=2, description="복귀지 [경도, 위도]")
    home: Optional[List[float]] = Field(None, min_length=2, max_length=2, description="자택 [경도, 위도]")
    center: Optional[List[float]] = Field(None, min_length=2, max_length=2, description="센터 [경도, 위도]")

    @field_validator("start", "end")
    @classmethod
    def validate_coord(cls, v):
        _validate_korea_coord(v[0], v[1], "기사 ")
        return v


class Crew(BaseModel):
    """기사 팀 구성"""
    size: Literal[1, 2] = Field(..., description="인원수 (1 또는 2)")
    type: Optional[CrewType] = Field(None, description="팀 유형 (1인/2인/1인팀/2인팀)")
    is_filler: bool = Field(False, description="합배차 가능 여부")
    can_joint_dispatch: bool = Field(False, description="합배차 대상 여부")


class AvoidModel(BaseModel):
    """미결 이력 모델"""
    model: str = Field(..., min_length=1, description="모델코드")
    date: Optional[str] = Field(None, description="미결 발생일")


class Exclusions(BaseModel):
    """기사 배정 제외 조건"""
    excluded_skus: List[str] = Field(default_factory=list, description="교육 미이수 SKU 목록")
    avoid_models: List[AvoidModel] = Field(default_factory=list, description="미결 이력 모델 목록 (C8)")


class FeeStatus(BaseModel):
    """기사 설치비 현황"""
    monthly_accumulated: int = Field(0, ge=0, description="당월 누적 설치비 (원)")
    daily_target: Optional[int] = Field(None, ge=0, description="일 목표 설치비 (원)")
    monthly_dispatch_days: Optional[int] = Field(None, ge=0, description="당월 배차 일수")


class WorkTime(BaseModel):
    """근무 시간"""
    start: Optional[str] = Field(None, description="시작 시각 (HH:MM)")
    end: Optional[str] = Field(None, description="종료 시각 (HH:MM)")
    breaks: Optional[List[Dict[str, str]]] = Field(None, description="휴게 시간 [{start, end}]")


class VehicleLimits(BaseModel):
    """기사 제한값"""
    max_orders: Optional[int] = Field(None, ge=1, description="최대 처리 건수")
    max_distance_km: Optional[float] = Field(None, ge=0, description="최대 이동 거리 (km)")
    max_work_minutes: Optional[int] = Field(None, ge=0, description="최대 근무 시간 (분)")


class VehicleCapabilities(BaseModel):
    """기사 역량 플래그"""
    model_config = ConfigDict(extra="allow")
    simple_delivery: bool = Field(False)
    simple_install: bool = Field(False)
    built_in_closet: bool = Field(False)
    sliding_closet: bool = Field(False)
    regular_closet: bool = Field(False)
    all_items: bool = Field(False)
    medium_difficulty: bool = Field(False)
    hanging: bool = Field(False)


class HglisVehicle(BaseModel):
    """HGLIS 기사 (래퍼 입력)"""
    model_config = ConfigDict(extra="allow")
    id: int = Field(..., gt=0, description="기사 고유 ID (양수)")
    driver_id: str = Field(..., min_length=1, description="기사ID")
    driver_name: Optional[str] = Field(None, description="기사명")
    grade: Grade = Field(..., description="기능도 S/A/B/C/D")
    service_grade: Grade = Field(..., description="서비스등급 S/A/B/C")
    capacity_cbm: float = Field(..., gt=0, description="적재 용량 CBM")
    location: VehicleLocation
    region_code: str = Field(..., description="소속 권역코드")
    crew: Crew
    # 구버전 호환 (신규 포맷은 exclusions 사용)
    new_product_restricted: bool = Field(False, description="신제품 배정 회피 (구버전 호환)")
    avoid_models: List[AvoidModel] = Field(default_factory=list, description="미결 이력 (구버전 호환)")
    # 신규 필드
    exclusions: Optional[Exclusions] = Field(None, description="배정 제외 조건 (C7/C8)")
    fee_status: FeeStatus = Field(default_factory=lambda: FeeStatus())
    work_time: Optional[WorkTime] = None
    limits: Optional[VehicleLimits] = None
    capabilities: Optional[VehicleCapabilities] = None
    is_rookie: bool = Field(False, description="신입 여부 (C7)")
    center_code: Optional[str] = Field(None, description="소속 센터")
    sub_region_code: Optional[str] = Field(None, description="세부 권역코드")

    @field_validator("region_code")
    @classmethod
    def validate_region(cls, v):
        if v not in VALID_REGIONS:
            raise ValueError(f"유효하지 않은 권역코드: {v} (허용: {VALID_REGIONS})")
        return v

    @property
    def effective_avoid_models(self) -> List[AvoidModel]:
        """실제 사용할 avoid_models (exclusions 우선)"""
        if self.exclusions is not None:
            return self.exclusions.avoid_models
        return self.avoid_models


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
    regions: Optional[List[str]] = Field(None, description="대상 권역 목록")
    source: Optional[str] = Field(None, description="요청 출처 (시뮬레이터 등)")


class DispatchConstraintConfig(BaseModel):
    """제약별 상세 설정 (constraint_config)"""
    model_config = ConfigDict(extra="allow")


class DispatchEngine(BaseModel):
    """엔진 파라미터"""
    calc_time_limit: int = Field(60, ge=1, description="최대 계산 시간 (초)")
    exploration_level: int = Field(5, ge=1, le=5, description="탐색 수준 (1~5)")
    balance_mode: str = Field("balanced", description="밸런스 모드")


class DispatchOptions(BaseModel):
    """배차 옵션"""
    model_config = ConfigDict(extra="allow")
    max_tasks_per_driver: int = Field(12, ge=1, description="기사 당 최대 건수")
    enable_joint_dispatch: bool = Field(False, description="합배차 활성화 (Phase 3)")
    geometry: bool = Field(True, description="경로 지오메트리 포함")
    # 신규: 명세서 기반 제약 플래그
    constraints: Optional[Dict[str, bool]] = Field(
        None, description="제약 활성화 플래그 {C1: true, ...}"
    )
    constraint_config: Optional[Dict[str, Any]] = Field(
        None, description="제약별 상세 설정"
    )
    engine: Optional[DispatchEngine] = Field(None, description="엔진 파라미터")


class HglisDispatchRequest(BaseModel):
    """POST /dispatch 요청 본문"""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "meta": {"date": "2026-03-01", "region_mode": "strict"},
                "vehicles": [
                    {
                        "id": 1, "driver_id": "D001", "driver_name": "김기사",
                        "grade": "A", "service_grade": "A",
                        "capacity_cbm": 12.0,
                        "location": {"start": [127.0276, 37.4979], "end": [127.0276, 37.4979]},
                        "region_code": "Y1",
                        "crew": {"size": 2, "is_filler": False},
                        "new_product_restricted": False, "avoid_models": [],
                        "fee_status": {"monthly_accumulated": 3000000}
                    }
                ],
                "jobs": [
                    {
                        "id": 1, "order_id": "ORD-001",
                        "location": [127.0500, 37.5172],
                        "region_code": "Y1",
                        "products": [
                            {"model_code": "REF-001", "model_name": "냉장고 500L",
                             "cbm": 2.5, "fee": 80000, "is_new_product": False,
                             "required_grade": "B", "quantity": 1}
                        ],
                        "scheduling": {"preferred_time_slot": "오전1", "service_minutes": 45},
                        "constraints": {"crew_type": "2인"},
                        "priority": {"level": 0, "is_urgent": False, "is_vip": False}
                    }
                ],
                "options": {"max_tasks_per_driver": 12, "geometry": True}
            }
        }
    )

    meta: DispatchMeta
    jobs: List[HglisJob] = Field(..., min_length=1, description="오더 목록")
    vehicles: List[HglisVehicle] = Field(..., min_length=1, description="기사 목록")
    options: DispatchOptions = Field(default_factory=lambda: DispatchOptions())


# --- 응답 ---

class DispatchResult(BaseModel):
    """개별 오더 배차 결과"""
    order_id: str
    model_name: Optional[str] = None  # products 기반 계산값
    dispatch_type: Literal["단독", "합배차_주", "합배차_보조"]
    driver_id: str
    driver_name: Optional[str] = None
    secondary_driver_id: Optional[str] = None
    secondary_driver_name: Optional[str] = None
    delivery_sequence: int
    scheduled_arrival: Optional[str] = None
    install_fee: int = 0
    geometry: Optional[Any] = None


class DriverSummary(BaseModel):
    """기사별 요약"""
    driver_id: str
    driver_name: Optional[str] = None
    grade: Grade
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
    reasons: List[Dict[str, Any]] = []


class HglisDispatchResponse(BaseModel):
    """POST /dispatch 응답"""
    status: Literal["success", "partial", "failed"]
    meta: Dict[str, Any]
    statistics: Dict[str, Any]
    results: List[DispatchResult] = []
    driver_summary: List[DriverSummary] = []
    unassigned: List[UnassignedJob] = []
    warnings: List[Dict[str, Any]] = []
    # 지도 표출용: VROOM 원본 routes (geometry 포함)
    routes: List[Dict[str, Any]] = []
    # 분석 결과 (ResultAnalyzer)
    analysis: Optional[Dict[str, Any]] = None
    # 디버그: 중간 VROOM 입출력 확인용
    debug: Optional[Dict[str, Any]] = Field(None, alias="debug")
