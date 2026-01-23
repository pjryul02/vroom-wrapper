# VROOM Wrapper v2.0 마스터 구현 로드맵

**작성일**: 2026-01-23
**목표**: 단순 미배정 사유 분석 → 완전한 VRP 최적화 플랫폼 진화

---

## 📋 목차

1. [전체 비전](#1-전체-비전)
2. [아키텍처 전략](#2-아키텍처-전략)
3. [Phase 0: 현재 상태 분석](#phase-0-현재-상태-분석-v10)
4. [Phase 1: 입력 전처리 계층](#phase-1-입력-전처리-계층-week-1-2)
5. [Phase 2: 통제 계층](#phase-2-통제-계층-week-3-5)
6. [Phase 3: 후처리 계층](#phase-3-후처리-계층-week-6-7)
7. [Phase 4: 확장 계층](#phase-4-확장-계층-week-8-10)
8. [Phase 5: 최적화 및 배포](#phase-5-최적화-및-배포-week-11-12)
9. [기술 스택 및 의존성](#기술-스택-및-의존성)
10. [테스트 전략](#테스트-전략)
11. [성능 목표](#성능-목표)
12. [운영 가이드](#운영-가이드)

---

## 1. 전체 비전

### 1.1 핵심 철학

**Wrapper는 VROOM의 "제어탑"이다**

```
VROOM = 최적화 엔진 (변경 불가, 블랙박스)
Wrapper = 지능형 제어 시스템 (완전한 통제)

┌───────────────────────────────────────────────────────┐
│  비즈니스 요구사항                                     │
│  (VIP 우선, 긴급 주문, 지역 제약, 실시간 교통 등)      │
└──────────────────┬────────────────────────────────────┘
                   │
                   ↓
┌───────────────────────────────────────────────────────┐
│  Wrapper v2.0 = 비즈니스 로직 + VROOM 제어            │
│  • 입력 정규화 및 검증                                 │
│  • 비즈니스 규칙 → VROOM 제약조건 변환                 │
│  • 다중 시나리오 최적화                                │
│  • 결과 품질 분석 및 개선 제안                         │
│  • 외부 시스템 통합 (날씨, 교통, ERP)                  │
└──────────────────┬────────────────────────────────────┘
                   │
                   ↓
┌───────────────────────────────────────────────────────┐
│  VROOM Engine (순수 최적화)                            │
│  • 입력 받기                                           │
│  • 최적 경로 계산                                      │
│  • 결과 반환                                           │
└───────────────────────────────────────────────────────┘
```

### 1.2 v1.0 vs v2.0 비교

| 측면 | v1.0 (현재) | v2.0 (목표) |
|-----|-----------|-----------|
| **입력 처리** | 그대로 전달 | 검증, 정규화, 변환 |
| **비즈니스 로직** | 없음 | VIP/긴급/지역 자동 적용 |
| **VROOM 제어** | 없음 | 동적 설정, 자동 튜닝 |
| **미배정 분석** | ✅ 사유 추적 | ✅ 개선 + 해결책 제안 |
| **결과 분석** | 없음 | 품질 점수, 비용 계산 |
| **외부 연동** | 없음 | 날씨, 교통, ERP, 지오코딩 |
| **캐싱** | 없음 | Redis 캐싱 |
| **인증/보안** | 없음 | API Key, Rate Limit |
| **모니터링** | 기본 로깅 | Prometheus, 상세 메트릭 |

---

## 2. 아키텍처 전략

### 2.1 레이어드 아키텍처 (5계층)

```
┌─────────────────────────────────────────────────────────────────┐
│ Layer 0: API Gateway (FastAPI)                                  │
│ • 인증/권한 (API Key)                                            │
│ • Rate Limiting                                                  │
│ • 요청 라우팅                                                     │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│ Layer 1: Pre-Processing (입력 전처리)                           │
│                                                                  │
│ ┌────────────────┐  ┌──────────────────┐  ┌──────────────────┐ │
│ │InputValidator  │→ │InputNormalizer   │→ │BusinessEngine    │ │
│ │(Pydantic 검증) │  │(좌표/시간 정규화) │  │(비즈니스 규칙)   │ │
│ └────────────────┘  └──────────────────┘  └──────────────────┘ │
│                                                                  │
│ ┌──────────────────────────────────────────────────────────┐   │
│ │ConstraintTransformer (비즈니스→VROOM 제약 변환)          │   │
│ └──────────────────────────────────────────────────────────┘   │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│ Layer 2: Control (최적화 제어)                                  │
│                                                                  │
│ ┌────────────────────────┐  ┌──────────────────────────────┐   │
│ │VROOMConfigManager      │  │OptimizationStrategy          │   │
│ │(동적 설정 생성)         │  │(단일/다중 시나리오 선택)      │   │
│ └────────────────────────┘  └──────────────────────────────┘   │
│                                                                  │
│ ┌────────────────────────┐  ┌──────────────────────────────┐   │
│ │ConstraintTuner         │  │MultiScenarioEngine           │   │
│ │(자동 제약조건 완화)     │  │(병렬 최적화 실행)             │   │
│ └────────────────────────┘  └──────────────────────────────┘   │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           │ call_vroom()
                           ↓
┌─────────────────────────────────────────────────────────────────┐
│                      VROOM Engine (Docker)                       │
│                      + OSRM (Docker)                             │
└──────────────────────────┬──────────────────────────────────────┘
                           │ result
                           ↓
┌──────────────────────────▼──────────────────────────────────────┐
│ Layer 3: Post-Processing (결과 후처리)                          │
│                                                                  │
│ ┌────────────────────┐  ┌────────────────┐  ┌───────────────┐  │
│ │ConstraintChecker   │  │ResultAnalyzer  │  │StatsGenerator │  │
│ │(미배정 사유 v1.0✅)│  │(품질 점수)     │  │(통계 생성)    │  │
│ └────────────────────┘  └────────────────┘  └───────────────┘  │
│                                                                  │
│ ┌────────────────────┐  ┌────────────────┐                     │
│ │CostCalculator      │  │RecommendEngine │                     │
│ │(비용/탄소 계산)    │  │(개선 제안)     │                     │
│ └────────────────────┘  └────────────────┘                     │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│ Layer 4: Extensions (확장 기능)                                 │
│                                                                  │
│ ┌──────────────────┐  ┌────────────────┐  ┌─────────────────┐  │
│ │ExternalAPI       │  │CacheManager    │  │MonitorCollector │  │
│ │(날씨/교통/ERP)   │  │(Redis)         │  │(Prometheus)     │  │
│ └──────────────────┘  └────────────────┘  └─────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 핵심 설계 원칙

#### 원칙 1: VROOM 블랙박스 유지
- ✅ VROOM 소스 코드 수정 **절대 금지**
- ✅ VROOM은 순수 최적화 엔진으로만 사용
- ✅ 모든 비즈니스 로직은 Wrapper에서 처리

#### 원칙 2: 레이어 독립성
- ✅ 각 레이어는 독립적으로 개발/테스트 가능
- ✅ 레이어 간 명확한 인터페이스
- ✅ 한 레이어 변경이 다른 레이어에 영향 최소화

#### 원칙 3: 점진적 진화
- ✅ v1.0 기능(미배정 사유) 유지
- ✅ Phase별 독립 개발 및 배포
- ✅ 하위 호환성 보장

#### 원칙 4: 성능 우선
- ✅ 각 레이어 오버헤드 < 100ms
- ✅ 캐싱으로 중복 연산 제거
- ✅ 병렬 처리 최대 활용

---

## Phase 0: 현재 상태 분석 (v1.0)

### 현재 구현된 기능

```python
# vroom_wrapper.py (v1.0) - 336줄

class ConstraintChecker:
    """미배정 작업 사유 분석"""

    def __init__(self, vrp_input):
        self.vehicles = vrp_input.get('vehicles', [])
        self.jobs = vrp_input.get('jobs', [])
        self.jobs_by_id = {job['id']: job for job in self.jobs}

    def analyze_unassigned(self, unassigned_list):
        """미배정 목록 분석"""
        reasons_map = {}
        for unassigned in unassigned_list:
            job = self.jobs_by_id[unassigned['id']]
            reasons = self._check_job_violations(job)
            reasons_map[unassigned['id']] = reasons
        return reasons_map

    def _check_job_violations(self, job):
        """개별 작업 제약 검사 (순서: Skills → Capacity → Time → MaxTasks)"""
        # 1. Skills 체크 (100% 정확도)
        # 2. Capacity 체크 (100% 정확도)
        # 3. Time Window 체크 (95% 정확도)
        # 4. Max Tasks 체크 (90% 정확도)
        pass

@app.post("/optimize")
async def optimize_with_reasons(vrp_input: Dict):
    checker = ConstraintChecker(vrp_input)
    result = call_vroom(vrp_input)

    if result.get('unassigned'):
        reasons_map = checker.analyze_unassigned(result['unassigned'])
        for unassigned in result['unassigned']:
            unassigned['reasons'] = reasons_map[unassigned['id']]

    return result
```

### 현재의 강점
1. ✅ 미배정 사유 분석 작동 (Skills, Capacity, TimeWindow, MaxTasks)
2. ✅ FastAPI 기반 RESTful API
3. ✅ Health check 엔드포인트
4. ✅ 기본 로깅
5. ✅ Docker 환경 (OSRM + VROOM) 구축 완료

### 현재의 한계
1. ❌ 입력 검증 없음 (잘못된 데이터도 그대로 전달)
2. ❌ 좌표/시간 형식 제한 (VROOM 표준만 가능)
3. ❌ 비즈니스 로직 없음 (VIP, 긴급 등 수동 처리)
4. ❌ VROOM 설정 고정 (모든 요청에 동일 설정)
5. ❌ 결과 품질 분석 없음
6. ❌ 외부 시스템 연동 없음
7. ❌ 캐싱 없음
8. ❌ 인증/보안 없음

---

## Phase 1: 입력 전처리 계층 (Week 1-2)

### 1.1 목표
- ✅ 모든 입력을 검증하고 정규화
- ✅ 다양한 입력 형식 지원
- ✅ 비즈니스 규칙을 VROOM 제약조건으로 자동 변환

### 1.2 구현 컴포넌트

#### 1.2.1 InputValidator (Pydantic 모델)

**목적**: 타입 안전성 + 자동 검증

```python
# models.py (새 파일)

from pydantic import BaseModel, validator, Field
from typing import List, Optional

class Location(BaseModel):
    """좌표 검증 (한국 영역)"""
    lon: float = Field(..., ge=124, le=132)
    lat: float = Field(..., ge=33, le=43)

    @classmethod
    def from_list(cls, coords: List[float]):
        """[lon, lat] → Location 객체"""
        return cls(lon=coords[0], lat=coords[1])

class TimeWindow(BaseModel):
    """시간창 검증"""
    start: int = Field(..., ge=0, description="Start time (seconds)")
    end: int = Field(..., ge=0, description="End time (seconds)")

    @validator('end')
    def end_after_start(cls, v, values):
        if 'start' in values and v <= values['start']:
            raise ValueError('End time must be after start time')
        return v

class Break(BaseModel):
    """휴식 시간"""
    id: int
    time_windows: List[List[int]]
    service: int
    description: Optional[str] = None

    @validator('time_windows')
    def validate_time_windows(cls, v):
        for tw in v:
            if len(tw) != 2:
                raise ValueError('Each time window must be [start, end]')
            TimeWindow(start=tw[0], end=tw[1])
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
    breaks: Optional[List[Break]] = []
    speed_factor: Optional[float] = Field(default=1.0, ge=0.1, le=2.0)
    description: Optional[str] = None

    @validator('start', 'end')
    def validate_location(cls, v):
        if v:
            Location.from_list(v)  # 검증
        return v

    @validator('end')
    def end_default_to_start(cls, v, values):
        """end 미지정 시 start로 복귀"""
        return v if v else values.get('start')

class Job(BaseModel):
    """작업 모델"""
    id: int
    location: List[float]
    service: int = Field(default=300, ge=0)  # 기본 5분
    delivery: Optional[List[int]] = None
    pickup: Optional[List[int]] = None
    skills: Optional[List[int]] = Field(default=[])
    priority: int = Field(default=0, ge=0, le=100)
    time_windows: Optional[List[List[int]]] = None
    description: Optional[str] = None

    @validator('location')
    def validate_location(cls, v):
        if len(v) != 2:
            raise ValueError('Location must be [lon, lat]')
        Location.from_list(v)
        return v

    @validator('time_windows')
    def validate_time_windows(cls, v):
        if v:
            for tw in v:
                if len(tw) != 2:
                    raise ValueError('Time window must be [start, end]')
                TimeWindow(start=tw[0], end=tw[1])
        return v

class Shipment(BaseModel):
    """배송 쌍 (pickup + delivery)"""
    id: int
    pickup: Job
    delivery: Job
    amount: List[int]
    skills: Optional[List[int]] = Field(default=[])
    priority: int = Field(default=0, ge=0, le=100)

class VRPInput(BaseModel):
    """전체 VRP 입력 검증"""
    vehicles: List[Vehicle]
    jobs: List[Job] = []
    shipments: List[Shipment] = []

    @validator('vehicles')
    def at_least_one_vehicle(cls, v):
        if not v:
            raise ValueError('At least one vehicle required')
        return v

    @validator('jobs')
    def jobs_or_shipments_required(cls, v, values):
        if not v and not values.get('shipments'):
            raise ValueError('Either jobs or shipments required')
        return v

    class Config:
        # 추가 필드 허용 (VROOM의 확장 필드)
        extra = "allow"

# FastAPI 엔드포인트에 적용
@app.post("/optimize")
async def optimize_with_validation(vrp_input: VRPInput):
    """Pydantic이 자동으로 검증"""
    vrp_dict = vrp_input.dict()
    return await optimize_core(vrp_dict)
```

**검증 예시**:

```python
# 테스트 케이스 1: 잘못된 좌표 → 자동 거부
invalid_input = {
    "vehicles": [{"id": 1, "start": [200, 100]}],  # lon=200 (범위 초과)
    "jobs": [{"id": 1, "location": [127, 37]}]
}

# FastAPI가 자동으로 400 에러 반환:
# {
#   "detail": [
#     {
#       "loc": ["vehicles", 0, "start"],
#       "msg": "Longitude must be in Korea bounds (124-132)",
#       "type": "value_error"
#     }
#   ]
# }

# 테스트 케이스 2: 시간창 오류 → 자동 거부
invalid_time = {
    "vehicles": [{"id": 1, "start": [127, 37]}],
    "jobs": [{"id": 1, "location": [127, 37], "time_windows": [[10000, 5000]]}]  # end < start
}
# → "End time must be after start time"
```

#### 1.2.2 InputNormalizer

**목적**: 다양한 형식 → VROOM 표준 형식

```python
# normalizer.py (새 파일)

from typing import Any, Dict, List, Union
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class InputNormalizer:
    """입력 데이터 정규화"""

    def normalize(self, vrp_input: Dict) -> Dict:
        """전체 정규화 파이프라인"""
        logger.info("Starting input normalization")

        vrp_input = self._normalize_coordinates(vrp_input)
        vrp_input = self._normalize_time_format(vrp_input)
        vrp_input = self._add_missing_defaults(vrp_input)
        vrp_input = self._normalize_capacity_format(vrp_input)
        vrp_input = self._normalize_priority(vrp_input)

        logger.info("Input normalization completed")
        return vrp_input

    def _normalize_coordinates(self, vrp_input: Dict) -> Dict:
        """
        좌표 형식 정규화
        지원 형식:
        1. [lon, lat]           (VROOM 표준)
        2. {"lon": x, "lat": y}
        3. {"longitude": x, "latitude": y}
        4. {"x": lon, "y": lat}
        """
        for job in vrp_input.get('jobs', []):
            job['location'] = self._to_lon_lat(job['location'])

        for vehicle in vrp_input.get('vehicles', []):
            vehicle['start'] = self._to_lon_lat(vehicle['start'])
            if 'end' in vehicle:
                vehicle['end'] = self._to_lon_lat(vehicle['end'])

        for shipment in vrp_input.get('shipments', []):
            if 'pickup' in shipment:
                shipment['pickup']['location'] = self._to_lon_lat(
                    shipment['pickup']['location']
                )
            if 'delivery' in shipment:
                shipment['delivery']['location'] = self._to_lon_lat(
                    shipment['delivery']['location']
                )

        return vrp_input

    def _to_lon_lat(self, location: Any) -> List[float]:
        """다양한 좌표 형식 → [lon, lat]"""
        if isinstance(location, list):
            if len(location) == 2:
                return [float(location[0]), float(location[1])]
            raise ValueError(f"Invalid list location: {location}")

        if isinstance(location, dict):
            # {"lon": x, "lat": y}
            if 'lon' in location and 'lat' in location:
                return [float(location['lon']), float(location['lat'])]

            # {"longitude": x, "latitude": y}
            if 'longitude' in location and 'latitude' in location:
                return [float(location['longitude']), float(location['latitude'])]

            # {"x": lon, "y": lat}
            if 'x' in location and 'y' in location:
                return [float(location['x']), float(location['y'])]

            raise ValueError(f"Invalid dict location: {location}")

        raise ValueError(f"Unsupported location type: {type(location)}")

    def _normalize_time_format(self, vrp_input: Dict) -> Dict:
        """
        시간 형식 정규화 → 초(seconds)
        지원 형식:
        1. int (seconds)        (VROOM 표준)
        2. "HH:MM"
        3. "HH:MM:SS"
        4. ISO 8601 timestamp   ("2024-01-23T09:30:00")
        5. Unix timestamp       (1706000000)
        """
        # Jobs
        for job in vrp_input.get('jobs', []):
            if 'time_windows' in job:
                job['time_windows'] = [
                    [self._to_seconds(tw[0]), self._to_seconds(tw[1])]
                    for tw in job['time_windows']
                ]

        # Vehicles
        for vehicle in vrp_input.get('vehicles', []):
            if 'time_window' in vehicle:
                tw = vehicle['time_window']
                vehicle['time_window'] = [
                    self._to_seconds(tw[0]),
                    self._to_seconds(tw[1])
                ]

            # Breaks
            if 'breaks' in vehicle:
                for br in vehicle['breaks']:
                    br['time_windows'] = [
                        [self._to_seconds(tw[0]), self._to_seconds(tw[1])]
                        for tw in br['time_windows']
                    ]

        # Shipments
        for shipment in vrp_input.get('shipments', []):
            for key in ['pickup', 'delivery']:
                if key in shipment and 'time_windows' in shipment[key]:
                    shipment[key]['time_windows'] = [
                        [self._to_seconds(tw[0]), self._to_seconds(tw[1])]
                        for tw in shipment[key]['time_windows']
                    ]

        return vrp_input

    def _to_seconds(self, time_value: Any) -> int:
        """다양한 시간 형식 → 초(seconds)"""
        if isinstance(time_value, int):
            # 이미 초 단위 (또는 Unix timestamp)
            # Unix timestamp는 너무 큼 (> 1,000,000,000)
            if time_value > 1_000_000_000:
                # Unix timestamp → 하루 시작부터 초
                dt = datetime.fromtimestamp(time_value)
                return dt.hour * 3600 + dt.minute * 60 + dt.second
            return time_value

        if isinstance(time_value, str):
            # "09:30" 또는 "09:30:00"
            if ':' in time_value:
                parts = time_value.split(':')
                h = int(parts[0])
                m = int(parts[1])
                s = int(parts[2]) if len(parts) > 2 else 0
                return h * 3600 + m * 60 + s

            # ISO 8601 ("2024-01-23T09:30:00")
            if 'T' in time_value or '-' in time_value:
                dt = datetime.fromisoformat(time_value)
                return dt.hour * 3600 + dt.minute * 60 + dt.second

        raise ValueError(f"Unsupported time format: {time_value}")

    def _add_missing_defaults(self, vrp_input: Dict) -> Dict:
        """누락된 필드에 합리적인 기본값 추가"""
        # Jobs
        for job in vrp_input.get('jobs', []):
            job.setdefault('service', 300)  # 기본 5분
            job.setdefault('priority', 0)
            job.setdefault('skills', [])

        # Vehicles
        for vehicle in vrp_input.get('vehicles', []):
            vehicle.setdefault('capacity', [1000])
            vehicle.setdefault('skills', [])

            # end 미지정 시 start로 복귀
            if 'end' not in vehicle:
                vehicle['end'] = vehicle['start'].copy()

        return vrp_input

    def _normalize_capacity_format(self, vrp_input: Dict) -> Dict:
        """용량 형식 정규화 (단일 값 → 리스트)"""
        # Vehicles
        for vehicle in vrp_input.get('vehicles', []):
            if 'capacity' in vehicle:
                cap = vehicle['capacity']
                if isinstance(cap, (int, float)):
                    vehicle['capacity'] = [int(cap)]

        # Jobs
        for job in vrp_input.get('jobs', []):
            for key in ['delivery', 'pickup']:
                if key in job:
                    val = job[key]
                    if isinstance(val, (int, float)):
                        job[key] = [int(val)]

        # Shipments
        for shipment in vrp_input.get('shipments', []):
            if 'amount' in shipment:
                amt = shipment['amount']
                if isinstance(amt, (int, float)):
                    shipment['amount'] = [int(amt)]

        return vrp_input

    def _normalize_priority(self, vrp_input: Dict) -> Dict:
        """우선순위 정규화 (0-100 범위)"""
        for job in vrp_input.get('jobs', []):
            if 'priority' in job:
                job['priority'] = max(0, min(100, int(job['priority'])))

        for shipment in vrp_input.get('shipments', []):
            if 'priority' in shipment:
                shipment['priority'] = max(0, min(100, int(shipment['priority'])))

        return vrp_input
```

**정규화 예시**:

```python
# 입력 (다양한 형식)
messy_input = {
    "vehicles": [{
        "id": 1,
        "start": {"longitude": 126.9780, "latitude": 37.5665},  # dict 형식
        "capacity": 100,  # 단일 값
        "time_window": ["09:00", "18:00"]  # "HH:MM" 형식
    }],
    "jobs": [{
        "id": 101,
        "location": {"lon": 127.0276, "lat": 37.4979},  # dict 형식
        "delivery": 50,  # 단일 값
        "time_windows": [["2024-01-23T09:00:00", "2024-01-23T10:00:00"]]  # ISO 8601
    }]
}

normalizer = InputNormalizer()
clean_input = normalizer.normalize(messy_input)

# 출력 (VROOM 표준)
clean_input == {
    "vehicles": [{
        "id": 1,
        "start": [126.9780, 37.5665],  # [lon, lat]
        "end": [126.9780, 37.5665],  # 자동 추가
        "capacity": [100],  # 리스트
        "time_window": [32400, 64800],  # 초 단위
        "skills": []  # 자동 추가
    }],
    "jobs": [{
        "id": 101,
        "location": [127.0276, 37.4979],  # [lon, lat]
        "delivery": [50],  # 리스트
        "time_windows": [[32400, 36000]],  # 초 단위
        "service": 300,  # 자동 추가
        "priority": 0,  # 자동 추가
        "skills": []  # 자동 추가
    }]
}
```

#### 1.2.3 BusinessRuleEngine

**목적**: 비즈니스 규칙을 VROOM 제약조건으로 자동 변환

```python
# business_rules.py (새 파일)

from typing import Dict, List, Any
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

@dataclass
class Zone:
    """지역 정의"""
    name: str
    bounds: List[float]  # [lon_min, lat_min, lon_max, lat_max]
    allowed_vehicles: List[int]  # 허용 차량 ID
    skill_id: int  # 자동 생성된 skill ID

@dataclass
class Specialization:
    """차량 특수 능력"""
    name: str  # 예: "refrigerated", "heavy_duty"
    vehicle_ids: List[int]
    job_types: List[str]  # 예: ["frozen", "cold"]
    skill_id: int

class BusinessRuleEngine:
    """비즈니스 규칙 엔진"""

    def __init__(self):
        self.zone_skill_base = 10000  # 지역 skill ID 시작
        self.spec_skill_base = 20000  # 특수 능력 skill ID 시작

    def apply_rules(self, vrp_input: Dict, rules: Dict[str, Any]) -> Dict:
        """
        비즈니스 규칙 적용

        rules = {
            "vip_priority_boost": True,
            "urgent_time_preference": True,
            "zone_restrictions": {...},
            "driver_specialization": {...},
            "auto_break_injection": True,
            "lunch_break_time": [43200, 46800],  # 12:00-13:00
            "max_working_hours": 32400,  # 9시간
        }
        """
        logger.info(f"Applying business rules: {list(rules.keys())}")

        if rules.get('vip_priority_boost'):
            vrp_input = self._boost_vip_priority(vrp_input)

        if rules.get('urgent_time_preference'):
            vrp_input = self._prefer_urgent_time(vrp_input)

        if 'zone_restrictions' in rules:
            vrp_input = self._apply_zone_restrictions(
                vrp_input,
                rules['zone_restrictions']
            )

        if 'driver_specialization' in rules:
            vrp_input = self._apply_driver_skills(
                vrp_input,
                rules['driver_specialization']
            )

        if rules.get('auto_break_injection'):
            lunch_time = rules.get('lunch_break_time', [43200, 46800])
            vrp_input = self._inject_breaks(vrp_input, lunch_time)

        if 'max_working_hours' in rules:
            vrp_input = self._limit_working_hours(
                vrp_input,
                rules['max_working_hours']
            )

        logger.info("Business rules applied successfully")
        return vrp_input

    def _boost_vip_priority(self, vrp_input: Dict) -> Dict:
        """VIP 고객 우선순위 +50"""
        for job in vrp_input.get('jobs', []):
            if job.get('customer_type') == 'VIP':
                job['priority'] = min(100, job.get('priority', 0) + 50)
                logger.debug(f"Job {job['id']} boosted (VIP)")

        for shipment in vrp_input.get('shipments', []):
            if shipment.get('customer_type') == 'VIP':
                shipment['priority'] = min(100, shipment.get('priority', 0) + 50)
                logger.debug(f"Shipment {shipment['id']} boosted (VIP)")

        return vrp_input

    def _prefer_urgent_time(self, vrp_input: Dict) -> Dict:
        """긴급 주문 시간창 2시간 이내로 설정"""
        current_time = 32400  # TODO: 실제 현재 시간 사용

        for job in vrp_input.get('jobs', []):
            if job.get('is_urgent'):
                job['time_windows'] = [[current_time, current_time + 7200]]  # +2시간
                job['priority'] = min(100, job.get('priority', 0) + 30)
                logger.debug(f"Job {job['id']} marked as urgent")

        return vrp_input

    def _apply_zone_restrictions(self, vrp_input: Dict, zones_config: Dict) -> Dict:
        """
        지역별 차량 제한

        zones_config = {
            "gangnam": {
                "bounds": [126.9, 37.4, 127.1, 37.6],
                "vehicle_ids": [1, 2, 3]
            },
            "songpa": {
                "bounds": [127.0, 37.4, 127.2, 37.6],
                "vehicle_ids": [4, 5, 6]
            }
        }
        """
        zones = []
        for zone_name, config in zones_config.items():
            skill_id = self.zone_skill_base + hash(zone_name) % 10000
            zones.append(Zone(
                name=zone_name,
                bounds=config['bounds'],
                allowed_vehicles=config['vehicle_ids'],
                skill_id=skill_id
            ))

        # 지역 내 작업에 skill 할당
        for job in vrp_input.get('jobs', []):
            lon, lat = job['location']
            for zone in zones:
                if self._in_bounds(lon, lat, zone.bounds):
                    if zone.skill_id not in job.get('skills', []):
                        job.setdefault('skills', []).append(zone.skill_id)
                    logger.debug(f"Job {job['id']} assigned to zone {zone.name}")

        # 허용 차량에 skill 부여
        for zone in zones:
            for vehicle in vrp_input.get('vehicles', []):
                if vehicle['id'] in zone.allowed_vehicles:
                    if zone.skill_id not in vehicle.get('skills', []):
                        vehicle.setdefault('skills', []).append(zone.skill_id)

        return vrp_input

    def _in_bounds(self, lon: float, lat: float, bounds: List[float]) -> bool:
        """좌표가 경계 내에 있는지 확인"""
        lon_min, lat_min, lon_max, lat_max = bounds
        return lon_min <= lon <= lon_max and lat_min <= lat <= lat_max

    def _apply_driver_skills(self, vrp_input: Dict, specializations_config: Dict) -> Dict:
        """
        기사 특수 능력 적용

        specializations_config = {
            "refrigerated": {
                "vehicle_ids": [1, 3, 5],
                "job_types": ["frozen", "cold"]
            },
            "heavy_duty": {
                "vehicle_ids": [7, 8],
                "job_types": ["furniture", "appliance"]
            }
        }
        """
        specializations = []
        for spec_name, config in specializations_config.items():
            skill_id = self.spec_skill_base + hash(spec_name) % 10000
            specializations.append(Specialization(
                name=spec_name,
                vehicle_ids=config['vehicle_ids'],
                job_types=config['job_types'],
                skill_id=skill_id
            ))

        # 특수 차량에 skill 부여
        for spec in specializations:
            for vehicle in vrp_input.get('vehicles', []):
                if vehicle['id'] in spec.vehicle_ids:
                    if spec.skill_id not in vehicle.get('skills', []):
                        vehicle.setdefault('skills', []).append(spec.skill_id)
                    logger.debug(f"Vehicle {vehicle['id']} has {spec.name} skill")

        # 해당 타입 작업에 skill 요구
        for spec in specializations:
            for job in vrp_input.get('jobs', []):
                if job.get('product_type') in spec.job_types:
                    if spec.skill_id not in job.get('skills', []):
                        job.setdefault('skills', []).append(spec.skill_id)
                    logger.debug(f"Job {job['id']} requires {spec.name}")

        return vrp_input

    def _inject_breaks(self, vrp_input: Dict, lunch_time: List[int]) -> Dict:
        """차량에 휴식시간 자동 삽입"""
        for vehicle in vrp_input.get('vehicles', []):
            if 'breaks' not in vehicle or not vehicle['breaks']:
                vehicle['breaks'] = [{
                    'id': vehicle['id'] * 1000,
                    'time_windows': [lunch_time],
                    'service': 3600,  # 1시간
                    'description': '점심시간'
                }]
                logger.debug(f"Vehicle {vehicle['id']}: lunch break added")

        return vrp_input

    def _limit_working_hours(self, vrp_input: Dict, max_duration: int) -> Dict:
        """차량 최대 근무시간 제한"""
        for vehicle in vrp_input.get('vehicles', []):
            if 'time_window' in vehicle:
                start, end = vehicle['time_window']
                duration = end - start

                if duration > max_duration:
                    # 시작 시간은 유지하고 종료 시간을 제한
                    vehicle['time_window'] = [start, start + max_duration]
                    logger.debug(
                        f"Vehicle {vehicle['id']}: working hours limited to "
                        f"{max_duration / 3600:.1f} hours"
                    )

        return vrp_input
```

**비즈니스 규칙 적용 예시**:

```python
# 입력
vrp_input = {
    "vehicles": [
        {"id": 1, "start": [126.95, 37.55], "capacity": [100]},
        {"id": 2, "start": [127.05, 37.50], "capacity": [150]}
    ],
    "jobs": [
        {"id": 101, "location": [126.98, 37.52], "customer_type": "VIP"},
        {"id": 102, "location": [127.03, 37.48], "is_urgent": True},
        {"id": 103, "location": [126.92, 37.57], "product_type": "frozen"}
    ]
}

# 비즈니스 규칙
rules = {
    "vip_priority_boost": True,
    "urgent_time_preference": True,
    "zone_restrictions": {
        "gangnam": {
            "bounds": [126.9, 37.4, 127.0, 37.6],
            "vehicle_ids": [1]
        }
    },
    "driver_specialization": {
        "refrigerated": {
            "vehicle_ids": [2],
            "job_types": ["frozen", "cold"]
        }
    },
    "auto_break_injection": True
}

engine = BusinessRuleEngine()
result = engine.apply_rules(vrp_input, rules)

# 결과 (VROOM이 이해할 수 있는 제약조건으로 변환됨)
result == {
    "vehicles": [
        {
            "id": 1,
            "start": [126.95, 37.55],
            "capacity": [100],
            "skills": [10123],  # gangnam zone skill
            "breaks": [{"id": 1000, "time_windows": [[43200, 46800]], "service": 3600}]
        },
        {
            "id": 2,
            "start": [127.05, 37.50],
            "capacity": [150],
            "skills": [20456],  # refrigerated skill
            "breaks": [{"id": 2000, "time_windows": [[43200, 46800]], "service": 3600}]
        }
    ],
    "jobs": [
        {
            "id": 101,
            "location": [126.98, 37.52],
            "customer_type": "VIP",
            "priority": 50,  # VIP boost
            "skills": [10123]  # gangnam zone skill
        },
        {
            "id": 102,
            "location": [127.03, 37.48],
            "is_urgent": True,
            "priority": 30,  # urgent boost
            "time_windows": [[32400, 39600]]  # 2시간 내
        },
        {
            "id": 103,
            "location": [126.92, 37.57],
            "product_type": "frozen",
            "skills": [10123, 20456]  # gangnam + refrigerated
        }
    ]
}
```

### 1.3 Phase 1 통합

```python
# preprocessor.py (새 파일)

from models import VRPInput
from normalizer import InputNormalizer
from business_rules import BusinessRuleEngine
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

class PreProcessor:
    """전처리 통합 클래스"""

    def __init__(self):
        self.normalizer = InputNormalizer()
        self.business_engine = BusinessRuleEngine()

    def process(
        self,
        vrp_input: Dict,
        business_rules: Dict[str, Any] = None
    ) -> Dict:
        """
        전처리 파이프라인
        1. 정규화
        2. 비즈니스 규칙 적용
        3. 최종 검증
        """
        logger.info("Starting pre-processing")

        # 1. 정규화
        vrp_input = self.normalizer.normalize(vrp_input)

        # 2. 비즈니스 규칙 적용
        if business_rules:
            vrp_input = self.business_engine.apply_rules(vrp_input, business_rules)

        # 3. 최종 검증 (Pydantic)
        try:
            validated = VRPInput(**vrp_input)
            vrp_input = validated.dict()
        except Exception as e:
            logger.error(f"Validation error: {e}")
            raise

        logger.info("Pre-processing completed")
        return vrp_input

# FastAPI 엔드포인트 수정
from preprocessor import PreProcessor

preprocessor = PreProcessor()

@app.post("/optimize")
async def optimize_v2(
    vrp_input: Dict,
    business_rules: Dict[str, Any] = None
):
    """v2.0 엔드포인트 (전처리 추가)"""

    # 전처리
    processed_input = preprocessor.process(vrp_input, business_rules)

    # VROOM 호출 (기존 로직)
    result = call_vroom(processed_input)

    # 후처리 (기존 로직)
    if result.get('unassigned'):
        checker = ConstraintChecker(processed_input)
        reasons_map = checker.analyze_unassigned(result['unassigned'])
        for unassigned in result['unassigned']:
            unassigned['reasons'] = reasons_map[unassigned['id']]

    return result
```

### 1.4 Phase 1 테스트

```python
# tests/test_phase1.py

import pytest
from models import VRPInput, Vehicle, Job
from normalizer import InputNormalizer
from business_rules import BusinessRuleEngine

def test_validation_invalid_coordinates():
    """잘못된 좌표 검증"""
    with pytest.raises(ValueError):
        VRPInput(
            vehicles=[Vehicle(id=1, start=[200, 100])],  # lon=200 초과
            jobs=[Job(id=1, location=[127, 37])]
        )

def test_normalization_coordinates():
    """좌표 정규화"""
    normalizer = InputNormalizer()

    input_data = {
        "vehicles": [{"id": 1, "start": {"lon": 126.9, "lat": 37.5}}],
        "jobs": [{"id": 1, "location": {"longitude": 127.0, "latitude": 37.6}}]
    }

    result = normalizer.normalize(input_data)

    assert result['vehicles'][0]['start'] == [126.9, 37.5]
    assert result['jobs'][0]['location'] == [127.0, 37.6]

def test_normalization_time():
    """시간 정규화"""
    normalizer = InputNormalizer()

    input_data = {
        "vehicles": [{"id": 1, "start": [126.9, 37.5], "time_window": ["09:00", "18:00"]}],
        "jobs": [{"id": 1, "location": [127.0, 37.6]}]
    }

    result = normalizer.normalize(input_data)

    assert result['vehicles'][0]['time_window'] == [32400, 64800]

def test_business_rules_vip():
    """VIP 우선순위 부스트"""
    engine = BusinessRuleEngine()

    input_data = {
        "vehicles": [{"id": 1, "start": [126.9, 37.5]}],
        "jobs": [{"id": 1, "location": [127.0, 37.6], "customer_type": "VIP"}]
    }

    result = engine.apply_rules(input_data, {"vip_priority_boost": True})

    assert result['jobs'][0]['priority'] == 50

def test_business_rules_zone():
    """지역 제약 적용"""
    engine = BusinessRuleEngine()

    input_data = {
        "vehicles": [
            {"id": 1, "start": [126.9, 37.5]},
            {"id": 2, "start": [127.0, 37.5]}
        ],
        "jobs": [{"id": 1, "location": [126.95, 37.52]}]  # gangnam 내
    }

    rules = {
        "zone_restrictions": {
            "gangnam": {
                "bounds": [126.9, 37.4, 127.0, 37.6],
                "vehicle_ids": [1]
            }
        }
    }

    result = engine.apply_rules(input_data, rules)

    # Job에 gangnam skill 추가됨
    assert len(result['jobs'][0]['skills']) > 0

    # Vehicle 1에 gangnam skill 추가됨
    zone_skill = result['jobs'][0]['skills'][0]
    assert zone_skill in result['vehicles'][0]['skills']

    # Vehicle 2에는 gangnam skill 없음
    assert zone_skill not in result['vehicles'][1].get('skills', [])
```

### 1.5 Phase 1 마일스톤

**Week 1**:
- ✅ Day 1-2: Pydantic 모델 작성 (`models.py`)
- ✅ Day 3-4: InputNormalizer 구현 (`normalizer.py`)
- ✅ Day 5: 단위 테스트 작성

**Week 2**:
- ✅ Day 1-3: BusinessRuleEngine 구현 (`business_rules.py`)
- ✅ Day 4: PreProcessor 통합 (`preprocessor.py`)
- ✅ Day 5-7: 통합 테스트 및 문서화

---

## Phase 2: 통제 계층 (Week 3-5)

### 2.1 목표
- ✅ VROOM 설정을 동적으로 제어
- ✅ 제약조건 자동 조정 (미배정 최소화)
- ✅ 다중 시나리오 병렬 실행

### 2.2 구현 컴포넌트

#### 2.2.1 VROOMConfigManager

**목적**: 입력 규모에 맞는 최적 VROOM 설정 생성

```python
# vroom_config.py (새 파일)

import yaml
import subprocess
from pathlib import Path
from typing import Dict, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

@dataclass
class VROOMConfig:
    """VROOM 설정"""
    threads: int = 4
    explore: int = 5  # 0-5
    timeout: int = 120000  # milliseconds
    geometry: bool = True

    def to_cli_args(self) -> List[str]:
        """CLI 인자로 변환 (vroom 바이너리 직접 호출 시)"""
        return [
            '-t', str(self.threads),
            '-x', str(self.explore),
        ] + (['-g'] if self.geometry else [])

class VROOMConfigManager:
    """VROOM 설정 동적 관리"""

    CONFIG_PATH = Path("/home/shawn/vroom-conf/config.yml")

    def __init__(self):
        self.default_config = self._load_config()

    def _load_config(self) -> Dict:
        """현재 설정 로드"""
        if self.CONFIG_PATH.exists():
            with open(self.CONFIG_PATH) as f:
                return yaml.safe_load(f)
        return {}

    def optimize_for_scenario(
        self,
        num_jobs: int,
        num_vehicles: int,
        priority: str = 'balanced'
    ) -> VROOMConfig:
        """
        시나리오별 최적 설정 선택

        priority:
        - 'speed': 빠른 결과 (explore=1-2)
        - 'balanced': 균형 (explore=3-4)
        - 'quality': 최고 품질 (explore=5)
        """
        logger.info(
            f"Optimizing config for {num_jobs} jobs, "
            f"{num_vehicles} vehicles, priority={priority}"
        )

        # 기본 설정
        config = VROOMConfig()

        # 작업 규모에 따른 조정
        if num_jobs < 50:
            # 소규모: 최고 품질 가능
            config.threads = 4
            config.explore = 5
            config.timeout = 60000  # 1분

        elif num_jobs < 200:
            # 중규모: 균형
            config.threads = 6
            config.explore = 4
            config.timeout = 120000  # 2분

        elif num_jobs < 1000:
            # 대규모: 효율 우선
            config.threads = 8
            config.explore = 3
            config.timeout = 300000  # 5분

        else:
            # 초대규모: 속도 최우선
            config.threads = 8
            config.explore = 2
            config.timeout = 600000  # 10분

        # 우선순위 오버라이드
        if priority == 'speed':
            config.explore = max(1, config.explore - 2)
            config.timeout = config.timeout // 2

        elif priority == 'quality':
            config.explore = 5
            config.timeout = min(600000, config.timeout * 2)

        logger.info(f"Generated config: {config}")
        return config

    def apply_config(self, config: VROOMConfig):
        """
        설정 적용 (config.yml 수정 + VROOM 재시작)

        주의: VROOM 재시작은 비용이 크므로 자주 하지 말것
        """
        logger.warning("Applying config and restarting VROOM")

        # config.yml 수정
        current = self._load_config()
        current.setdefault('cliArgs', {})
        current['cliArgs'].update({
            'threads': config.threads,
            'explore': config.explore,
            'timeout': config.timeout,
            'geometry': config.geometry
        })

        with open(self.CONFIG_PATH, 'w') as f:
            yaml.dump(current, f)

        # VROOM 재시작
        try:
            subprocess.run(
                ['docker-compose', 'restart', 'vroom'],
                cwd='/home/shawn/vroom-wrapper-project',
                check=True,
                capture_output=True,
                timeout=30
            )
            logger.info("VROOM restarted successfully")

        except subprocess.TimeoutExpired:
            logger.error("VROOM restart timeout")
            raise RuntimeError("Failed to restart VROOM")

        except subprocess.CalledProcessError as e:
            logger.error(f"VROOM restart failed: {e}")
            raise
```

#### 2.2.2 ConstraintTuner

**목적**: 미배정이 많으면 제약조건 완화하여 재시도

```python
# constraint_tuner.py (새 파일)

from typing import Dict, List
from copy import deepcopy
import logging

logger = logging.getLogger(__name__)

class ConstraintTuner:
    """제약조건 자동 튜닝"""

    def __init__(self, max_iterations: int = 3):
        self.max_iterations = max_iterations

    def auto_tune(
        self,
        vrp_input: Dict,
        initial_result: Dict,
        target_assignment_rate: float = 0.95
    ) -> Dict:
        """
        미배정 비율이 높으면 제약조건 완화하여 재시도

        전략:
        1. 원인 분석 (skills/capacity/time_window)
        2. 가장 많은 원인부터 완화
        3. 재최적화
        4. 목표 달성 또는 max_iterations까지 반복
        """
        unassigned = initial_result.get('unassigned', [])
        total_jobs = len(vrp_input.get('jobs', [])) + len(vrp_input.get('shipments', []))

        if not unassigned:
            logger.info("No unassigned jobs, no tuning needed")
            return initial_result

        assignment_rate = (total_jobs - len(unassigned)) / total_jobs
        logger.info(
            f"Initial assignment rate: {assignment_rate:.2%} "
            f"({len(unassigned)} / {total_jobs} unassigned)"
        )

        if assignment_rate >= target_assignment_rate:
            logger.info("Assignment rate above target, no tuning needed")
            return initial_result

        # 반복 튜닝
        current_input = deepcopy(vrp_input)
        current_result = initial_result
        best_result = initial_result

        for iteration in range(self.max_iterations):
            logger.info(f"Tuning iteration {iteration + 1}/{self.max_iterations}")

            # 원인 분석
            reasons = self._analyze_reasons(current_input, current_result['unassigned'])

            if not reasons:
                logger.warning("Cannot identify unassignment reasons")
                break

            # 가장 많은 원인 완화
            top_reason = max(reasons, key=reasons.get)
            logger.info(f"Top reason: {top_reason} ({reasons[top_reason]} jobs)")

            if top_reason == 'time_window':
                current_input = self._relax_time_windows(current_input)

            elif top_reason == 'capacity':
                current_input = self._increase_capacity(current_input)

            elif top_reason == 'skills':
                current_input = self._relax_skills(current_input)

            elif top_reason == 'max_tasks':
                current_input = self._increase_max_tasks(current_input)

            else:
                logger.warning(f"Unknown reason type: {top_reason}")
                break

            # 재최적화
            current_result = call_vroom(current_input)

            # 개선 확인
            new_unassigned = len(current_result.get('unassigned', []))
            new_rate = (total_jobs - new_unassigned) / total_jobs

            logger.info(
                f"Iteration {iteration + 1}: "
                f"{new_rate:.2%} assignment ({new_unassigned} unassigned)"
            )

            # 더 나아졌으면 저장
            if new_unassigned < len(best_result.get('unassigned', [])):
                best_result = current_result
                logger.info("✓ Improvement found")

            # 목표 달성
            if new_rate >= target_assignment_rate:
                logger.info("✓ Target assignment rate achieved")
                break

            # 더 이상 개선 없음
            if new_unassigned == len(current_result.get('unassigned', [])):
                logger.info("No more improvement, stopping")
                break

        final_rate = (total_jobs - len(best_result.get('unassigned', []))) / total_jobs
        logger.info(f"Final assignment rate: {final_rate:.2%}")

        # 메타데이터 추가
        best_result['_tuning_info'] = {
            'iterations': iteration + 1,
            'initial_unassigned': len(unassigned),
            'final_unassigned': len(best_result.get('unassigned', [])),
            'improvement': len(unassigned) - len(best_result.get('unassigned', []))
        }

        return best_result

    def _analyze_reasons(self, vrp_input: Dict, unassigned: List) -> Dict[str, int]:
        """미배정 원인 통계"""
        from vroom_wrapper import ConstraintChecker

        checker = ConstraintChecker(vrp_input)
        reasons_count = {}

        for u in unassigned:
            job = checker.jobs_by_id.get(u['id'])
            if not job:
                continue

            reasons = checker._check_job_violations(job)

            for reason in reasons:
                reason_type = reason['type']
                reasons_count[reason_type] = reasons_count.get(reason_type, 0) + 1

        return reasons_count

    def _relax_time_windows(self, vrp_input: Dict, extend_by: int = 3600) -> Dict:
        """시간창 확장 (+1시간)"""
        logger.info(f"Relaxing time windows by {extend_by / 3600:.1f} hours")

        for job in vrp_input.get('jobs', []):
            if 'time_windows' in job:
                job['time_windows'] = [
                    [max(0, tw[0] - extend_by), tw[1] + extend_by]
                    for tw in job['time_windows']
                ]

        for vehicle in vrp_input.get('vehicles', []):
            if 'time_window' in vehicle:
                tw = vehicle['time_window']
                vehicle['time_window'] = [
                    max(0, tw[0] - extend_by),
                    tw[1] + extend_by
                ]

        return vrp_input

    def _increase_capacity(self, vrp_input: Dict, factor: float = 1.2) -> Dict:
        """차량 용량 20% 증가"""
        logger.info(f"Increasing vehicle capacity by {(factor - 1) * 100:.0f}%")

        for vehicle in vrp_input.get('vehicles', []):
            if 'capacity' in vehicle:
                vehicle['capacity'] = [
                    int(cap * factor) for cap in vehicle['capacity']
                ]

        return vrp_input

    def _relax_skills(self, vrp_input: Dict) -> Dict:
        """Skills 요구사항 완화"""
        logger.info("Relaxing skills requirements")

        for job in vrp_input.get('jobs', []):
            if 'skills' in job and len(job['skills']) > 1:
                # 가장 제한적인 skill 하나만 남김
                job['skills'] = job['skills'][:1]

        return vrp_input

    def _increase_max_tasks(self, vrp_input: Dict, increment: int = 5) -> Dict:
        """Max tasks 증가"""
        logger.info(f"Increasing max_tasks by {increment}")

        for vehicle in vrp_input.get('vehicles', []):
            if 'max_tasks' in vehicle:
                vehicle['max_tasks'] += increment
            else:
                vehicle['max_tasks'] = 50  # 제한 없던 경우 50으로 설정

        return vrp_input
```

#### 2.2.3 MultiScenarioEngine

**목적**: 여러 설정으로 병렬 최적화 후 최선 선택

```python
# multi_scenario.py (새 파일)

import asyncio
from concurrent.futures import ProcessPoolExecutor
from typing import Dict, List
from copy import deepcopy
import time
import logging

logger = logging.getLogger(__name__)

class MultiScenarioEngine:
    """다중 시나리오 최적화 엔진"""

    def __init__(self, max_workers: int = 4):
        self.executor = ProcessPoolExecutor(max_workers=max_workers)

    async def optimize_multi(self, vrp_input: Dict) -> Dict:
        """
        여러 시나리오를 병렬 실행하여 최고 결과 선택

        시나리오:
        1. speed: explore=1, timeout=30s
        2. balanced: explore=3, timeout=60s
        3. quality: explore=5, timeout=120s
        4. time_relaxed: explore=3, time_window +30min
        5. capacity_relaxed: explore=3, capacity +20%
        """
        logger.info("Starting multi-scenario optimization")

        scenarios = [
            {
                'name': 'speed',
                'config': VROOMConfig(threads=8, explore=1, timeout=30000),
                'modifiers': {}
            },
            {
                'name': 'balanced',
                'config': VROOMConfig(threads=6, explore=3, timeout=60000),
                'modifiers': {}
            },
            {
                'name': 'quality',
                'config': VROOMConfig(threads=4, explore=5, timeout=120000),
                'modifiers': {}
            },
            {
                'name': 'time_relaxed',
                'config': VROOMConfig(threads=6, explore=3, timeout=60000),
                'modifiers': {'time_window_extend': 1800}  # +30분
            },
            {
                'name': 'capacity_relaxed',
                'config': VROOMConfig(threads=6, explore=3, timeout=60000),
                'modifiers': {'capacity_factor': 1.2}  # +20%
            }
        ]

        # 병렬 실행
        tasks = []
        for scenario in scenarios:
            modified_input = self._apply_modifiers(
                deepcopy(vrp_input),
                scenario['modifiers']
            )
            task = self._run_scenario_async(modified_input, scenario)
            tasks.append(task)

        # 모든 시나리오 완료 대기
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 실패한 시나리오 필터링
        valid_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Scenario {scenarios[i]['name']} failed: {result}")
            else:
                valid_results.append(result)

        if not valid_results:
            raise RuntimeError("All scenarios failed")

        # 최적 결과 선택
        best_result = self._select_best_result(valid_results)

        logger.info(f"Best scenario: {best_result['scenario_name']}")

        return best_result

    def _apply_modifiers(self, vrp_input: Dict, modifiers: Dict) -> Dict:
        """시나리오별 입력 수정"""
        if 'time_window_extend' in modifiers:
            extend = modifiers['time_window_extend']
            for job in vrp_input.get('jobs', []):
                if 'time_windows' in job:
                    job['time_windows'] = [
                        [tw[0] - extend, tw[1] + extend]
                        for tw in job['time_windows']
                    ]

        if 'capacity_factor' in modifiers:
            factor = modifiers['capacity_factor']
            for vehicle in vrp_input.get('vehicles', []):
                if 'capacity' in vehicle:
                    vehicle['capacity'] = [
                        int(cap * factor) for cap in vehicle['capacity']
                    ]

        return vrp_input

    async def _run_scenario_async(self, vrp_input: Dict, scenario: Dict) -> Dict:
        """시나리오 비동기 실행"""
        loop = asyncio.get_event_loop()

        logger.info(f"Running scenario: {scenario['name']}")
        start_time = time.time()

        try:
            result = await loop.run_in_executor(
                self.executor,
                call_vroom_with_config,
                vrp_input,
                scenario['config']
            )

            duration = time.time() - start_time
            logger.info(
                f"Scenario {scenario['name']} completed in {duration:.2f}s "
                f"({len(result.get('unassigned', []))} unassigned)"
            )

            # 메타데이터 추가
            result['scenario_name'] = scenario['name']
            result['scenario_duration'] = duration

            return result

        except Exception as e:
            logger.error(f"Scenario {scenario['name']} error: {e}")
            raise

    def _select_best_result(self, results: List[Dict]) -> Dict:
        """
        최적 결과 선택

        평가 기준:
        1. 미배정 수 (가장 중요)
        2. 총 거리
        3. 총 시간
        """
        scored_results = []

        for result in results:
            score = self._calculate_score(result)
            scored_results.append((score, result))

        # 점수 내림차순 정렬
        scored_results.sort(key=lambda x: x[0], reverse=True)

        best_result = scored_results[0][1]

        # 모든 시나리오 비교 정보 추가
        best_result['_scenario_comparison'] = [
            {
                'scenario': r['scenario_name'],
                'score': s,
                'unassigned': len(r.get('unassigned', [])),
                'distance': r.get('summary', {}).get('distance', 0),
                'duration': r.get('summary', {}).get('duration', 0)
            }
            for s, r in scored_results
        ]

        return best_result

    def _calculate_score(self, result: Dict) -> float:
        """
        결과 점수 계산 (0-100)

        가중치:
        - 배정률: 60%
        - 거리: 20%
        - 시간: 20%
        """
        # 배정률
        total_jobs = (
            sum(len(r.get('steps', [])) - 2 for r in result.get('routes', []))
            + len(result.get('unassigned', []))
        )
        assigned_jobs = total_jobs - len(result.get('unassigned', []))
        assignment_rate = assigned_jobs / max(1, total_jobs)

        # 거리 점수 (짧을수록 좋음)
        total_distance = result.get('summary', {}).get('distance', 0)
        distance_score = max(0, 100 - total_distance / 10000)  # 100km당 -10점

        # 시간 점수 (짧을수록 좋음)
        total_duration = result.get('summary', {}).get('duration', 0)
        duration_score = max(0, 100 - total_duration / 36000)  # 10시간당 -10점

        # 가중 합계
        score = (
            assignment_rate * 100 * 0.6
            + distance_score * 0.2
            + duration_score * 0.2
        )

        return score
```

### 2.3 Phase 2 통합

```python
# controller.py (새 파일)

from vroom_config import VROOMConfigManager, VROOMConfig
from constraint_tuner import ConstraintTuner
from multi_scenario import MultiScenarioEngine
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

class OptimizationController:
    """최적화 제어 통합"""

    def __init__(self):
        self.config_manager = VROOMConfigManager()
        self.tuner = ConstraintTuner(max_iterations=3)
        self.multi_scenario = MultiScenarioEngine(max_workers=4)

    async def optimize(
        self,
        vrp_input: Dict,
        strategy: str = 'single',  # 'single' | 'multi' | 'auto_tune'
        priority: str = 'balanced'  # 'speed' | 'balanced' | 'quality'
    ) -> Dict:
        """
        최적화 실행

        strategy:
        - 'single': 단일 최적화 (빠름)
        - 'multi': 다중 시나리오 병렬 (느리지만 최고 품질)
        - 'auto_tune': 자동 튜닝 (미배정 최소화)
        """
        num_jobs = len(vrp_input.get('jobs', []))
        num_vehicles = len(vrp_input.get('vehicles', []))

        logger.info(
            f"Optimization: {num_jobs} jobs, {num_vehicles} vehicles, "
            f"strategy={strategy}, priority={priority}"
        )

        if strategy == 'single':
            return await self._optimize_single(vrp_input, priority)

        elif strategy == 'multi':
            return await self._optimize_multi(vrp_input)

        elif strategy == 'auto_tune':
            return await self._optimize_auto_tune(vrp_input, priority)

        else:
            raise ValueError(f"Unknown strategy: {strategy}")

    async def _optimize_single(self, vrp_input: Dict, priority: str) -> Dict:
        """단일 최적화"""
        # 최적 설정 선택
        config = self.config_manager.optimize_for_scenario(
            len(vrp_input.get('jobs', [])),
            len(vrp_input.get('vehicles', [])),
            priority
        )

        # VROOM 호출
        result = call_vroom_with_config(vrp_input, config)

        result['_optimization_info'] = {
            'strategy': 'single',
            'config': config.__dict__
        }

        return result

    async def _optimize_multi(self, vrp_input: Dict) -> Dict:
        """다중 시나리오"""
        result = await self.multi_scenario.optimize_multi(vrp_input)

        result['_optimization_info'] = {
            'strategy': 'multi'
        }

        return result

    async def _optimize_auto_tune(self, vrp_input: Dict, priority: str) -> Dict:
        """자동 튜닝"""
        # 초기 최적화
        initial_result = await self._optimize_single(vrp_input, priority)

        # 튜닝
        final_result = self.tuner.auto_tune(vrp_input, initial_result)

        final_result['_optimization_info'] = {
            'strategy': 'auto_tune'
        }

        return final_result

# FastAPI 엔드포인트 수정
from controller import OptimizationController

controller = OptimizationController()

@app.post("/optimize/v2")
async def optimize_v2(
    vrp_input: Dict,
    strategy: str = 'single',
    priority: str = 'balanced',
    business_rules: Optional[Dict] = None
):
    """v2.0 최적화 엔드포인트"""

    # 전처리
    if business_rules:
        vrp_input = preprocessor.process(vrp_input, business_rules)

    # 최적화 (제어)
    result = await controller.optimize(vrp_input, strategy, priority)

    # 후처리 (미배정 사유)
    if result.get('unassigned'):
        checker = ConstraintChecker(vrp_input)
        reasons_map = checker.analyze_unassigned(result['unassigned'])
        for unassigned in result['unassigned']:
            unassigned['reasons'] = reasons_map[unassigned['id']]

    return result
```

### 2.4 Phase 2 테스트

```python
# tests/test_phase2.py

import pytest
from vroom_config import VROOMConfigManager
from constraint_tuner import ConstraintTuner

def test_config_small_scenario():
    """소규모 시나리오 설정"""
    manager = VROOMConfigManager()

    config = manager.optimize_for_scenario(30, 5, priority='quality')

    assert config.threads == 4
    assert config.explore == 5
    assert config.timeout == 60000

def test_config_large_scenario():
    """대규모 시나리오 설정"""
    manager = VROOMConfigManager()

    config = manager.optimize_for_scenario(1500, 200, priority='speed')

    assert config.threads == 8
    assert config.explore <= 2
    assert config.timeout <= 300000

@pytest.mark.asyncio
async def test_multi_scenario():
    """다중 시나리오 실행"""
    engine = MultiScenarioEngine(max_workers=2)

    vrp_input = {
        "vehicles": [{"id": 1, "start": [126.9, 37.5], "capacity": [100]}],
        "jobs": [
            {"id": 1, "location": [127.0, 37.6], "delivery": [50]},
            {"id": 2, "location": [126.8, 37.4], "delivery": [60]}
        ]
    }

    result = await engine.optimize_multi(vrp_input)

    assert 'scenario_name' in result
    assert '_scenario_comparison' in result
    assert len(result['_scenario_comparison']) > 1

def test_constraint_tuner():
    """제약조건 튜닝"""
    tuner = ConstraintTuner(max_iterations=2)

    vrp_input = {
        "vehicles": [{"id": 1, "start": [126.9, 37.5], "capacity": [50]}],
        "jobs": [
            {"id": 1, "location": [127.0, 37.6], "delivery": [30]},
            {"id": 2, "location": [126.8, 37.4], "delivery": [40]}  # 초과
        ]
    }

    initial_result = {
        "routes": [...],
        "unassigned": [{"id": 2, "location": [126.8, 37.4]}]
    }

    tuned_result = tuner.auto_tune(vrp_input, initial_result)

    # 튜닝 정보 있음
    assert '_tuning_info' in tuned_result

    # 미배정 감소 (capacity 증가로 해결)
    assert len(tuned_result['unassigned']) < len(initial_result['unassigned'])
```

### 2.5 Phase 2 마일스톤

**Week 3**:
- ✅ Day 1-2: VROOMConfigManager 구현
- ✅ Day 3-4: ConstraintTuner 구현
- ✅ Day 5: 단위 테스트

**Week 4**:
- ✅ Day 1-3: MultiScenarioEngine 구현
- ✅ Day 4-5: OptimizationController 통합

**Week 5**:
- ✅ Day 1-3: 통합 테스트 (실제 대규모 데이터)
- ✅ Day 4-5: 성능 튜닝 및 문서화

---

## Phase 3: 후처리 계층 (Week 6-7)

### 3.1 목표
- ✅ 결과 품질 분석 (점수, 효율성)
- ✅ 통계 생성 (차량별, 시간대별, 지역별)
- ✅ 비용 계산 (유류비, 인건비, 탄소 배출)
- ✅ 개선 제안 (추천 시스템)

**(상세 구현 코드는 WRAPPER-IMPLEMENTATION-PLAN.md의 Phase 3 참조)**

### 3.2 구현 컴포넌트
1. ResultAnalyzer (품질 점수 0-100)
2. StatisticsGenerator (차량/시간/지역별 통계)
3. CostCalculator (비용 및 탄소 계산)
4. RecommendationEngine (개선 제안)

---

## Phase 4: 확장 계층 (Week 8-10)

### 4.1 목표
- ✅ 외부 시스템 연동 (날씨, 교통, ERP, 지오코딩)
- ✅ 캐싱 (Redis)
- ✅ 인증/보안 (API Key, Rate Limiting)
- ✅ 모니터링 (Prometheus)

### 4.2 핵심 컴포넌트

#### 4.2.1 ExternalAPIIntegrator

**핵심 아이디어**:

OSRM은 **정적인 도로망 벡터 데이터만** 가지고 있습니다. 실시간 정보는 외부 API로 보완해야 합니다.

```python
# external_api.py

import httpx
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

class ExternalAPIIntegrator:
    """외부 API 연동"""

    def __init__(self):
        self.kakao_api_key = os.getenv('KAKAO_API_KEY')
        self.weather_api_key = os.getenv('WEATHER_API_KEY')
        self.traffic_api_key = os.getenv('TRAFFIC_API_KEY')

    async def enrich_with_external_data(self, vrp_input: Dict) -> Dict:
        """외부 데이터로 입력 강화"""

        # 1. 날씨 정보 추가 (악천후 시 서비스 시간 증가)
        vrp_input = await self._add_weather_info(vrp_input)

        # 2. 실시간 교통 정보 반영 (혼잡 지역 회피 또는 시간 조정)
        vrp_input = await self._adjust_for_traffic(vrp_input)

        # 3. 주소 -> 좌표 변환 (Kakao Local API)
        vrp_input = await self._geocode_addresses(vrp_input)

        return vrp_input

    async def _add_weather_info(self, vrp_input: Dict) -> Dict:
        """
        날씨 정보 추가

        악천후 시:
        - 서비스 시간 20% 증가
        - 차량 속도 10% 감소 (speed_factor)
        """
        # 대표 좌표 (첫 번째 차량 시작점)
        if not vrp_input.get('vehicles'):
            return vrp_input

        lon, lat = vrp_input['vehicles'][0]['start']

        try:
            async with httpx.AsyncClient() as client:
                # OpenWeatherMap API (무료 플랜)
                response = await client.get(
                    "https://api.openweathermap.org/data/2.5/weather",
                    params={
                        'lat': lat,
                        'lon': lon,
                        'appid': self.weather_api_key
                    },
                    timeout=5.0
                )
                weather = response.json()

            main_weather = weather.get('weather', [{}])[0].get('main', '')

            if main_weather in ['Rain', 'Snow', 'Thunderstorm']:
                logger.warning(f"Bad weather detected: {main_weather}")

                # 서비스 시간 20% 증가
                for job in vrp_input.get('jobs', []):
                    job['service'] = int(job.get('service', 300) * 1.2)

                # 차량 속도 10% 감소
                for vehicle in vrp_input.get('vehicles', []):
                    vehicle['speed_factor'] = vehicle.get('speed_factor', 1.0) * 0.9

        except Exception as e:
            logger.error(f"Weather API error: {e}")

        return vrp_input

    async def _adjust_for_traffic(self, vrp_input: Dict) -> Dict:
        """
        실시간 교통 정보 반영

        OSRM은 정적 도로망만 가지므로, 실시간 교통 정보는
        외부 API (Google/Kakao/TomTom)에서 가져와야 함

        전략:
        1. 주요 구간의 실시간 혼잡도 조회
        2. 혼잡 구간 포함 작업은 시간창 조정
        3. 또는 작업 우선순위 낮춤 (나중에 처리)
        """
        # TODO: 실제 교통 API 연동
        # 예: Kakao Mobility API, Google Maps Traffic

        logger.info("Traffic adjustment not implemented yet")
        return vrp_input

    async def _geocode_addresses(self, vrp_input: Dict) -> Dict:
        """
        주소 -> 좌표 변환 (Kakao Local API)

        사용자가 "서울시 강남구 테헤란로 123"처럼 주소로
        입력한 경우 좌표로 변환
        """
        async with httpx.AsyncClient() as client:
            for job in vrp_input.get('jobs', []):
                if 'address' in job and 'location' not in job:
                    try:
                        response = await client.get(
                            "https://dapi.kakao.com/v2/local/search/address.json",
                            headers={'Authorization': f'KakaoAK {self.kakao_api_key}'},
                            params={'query': job['address']},
                            timeout=3.0
                        )
                        result = response.json()

                        if result.get('documents'):
                            doc = result['documents'][0]
                            job['location'] = [float(doc['x']), float(doc['y'])]
                            logger.debug(f"Geocoded: {job['address']} -> {job['location']}")

                    except Exception as e:
                        logger.error(f"Geocoding error for {job['address']}: {e}")

        return vrp_input
```

**(상세 구현 코드는 WRAPPER-IMPLEMENTATION-PLAN.md의 Phase 4 참조)**

---

## Phase 5: 최적화 및 배포 (Week 11-12)

### 5.1 전체 파이프라인 통합

```python
# main.py (최종 통합)

from fastapi import FastAPI, HTTPException, Depends, Header, Request
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from typing import Dict, Optional
import time
import logging

from preprocessor import PreProcessor
from controller import OptimizationController
from result_analyzer import ResultAnalyzer
from statistics_generator import StatisticsGenerator
from external_api import ExternalAPIIntegrator
from cache_manager import CacheManager
from vroom_wrapper import ConstraintChecker

# FastAPI 앱
app = FastAPI(title="VROOM Wrapper v2.0", version="2.0")

# Rate Limiter
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# 컴포넌트 초기화
preprocessor = PreProcessor()
controller = OptimizationController()
analyzer = ResultAnalyzer()
stats_gen = StatisticsGenerator()
external_api = ExternalAPIIntegrator()
cache_manager = CacheManager()

# 로깅
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# API Key 검증
API_KEYS = {
    "client1-key-abc123": {"name": "Client 1", "rate_limit": "100/hour"},
    "client2-key-xyz789": {"name": "Client 2", "rate_limit": "50/hour"}
}

def verify_api_key(x_api_key: str = Header(None)) -> Dict:
    """API Key 검증"""
    if x_api_key not in API_KEYS:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return API_KEYS[x_api_key]

@app.post("/optimize/v2")
@limiter.limit("100/hour")
async def optimize_v2_full(
    request: Request,
    vrp_input: Dict,
    strategy: str = 'single',  # 'single' | 'multi' | 'auto_tune'
    priority: str = 'balanced',  # 'speed' | 'balanced' | 'quality'
    use_cache: bool = True,
    use_external_apis: bool = False,
    business_rules: Optional[Dict] = None,
    api_key_info: Dict = Depends(verify_api_key)
):
    """
    v2.0 완전한 최적화 파이프라인

    Parameters:
    - strategy: 최적화 전략
    - priority: 우선순위
    - use_cache: 캐싱 사용
    - use_external_apis: 외부 API 연동 (날씨/교통/지오코딩)
    - business_rules: 비즈니스 규칙
    """
    start_time = time.time()
    logger.info(f"Request from {api_key_info['name']}")

    try:
        # 0. 캐시 확인
        if use_cache:
            cached = cache_manager.get(vrp_input)
            if cached:
                logger.info("✓ Cache hit")
                cached['_metadata']['from_cache'] = True
                return cached

        # 1. 전처리
        vrp_input = preprocessor.process(vrp_input, business_rules)

        # 2. 외부 API 연동 (옵션)
        if use_external_apis:
            vrp_input = await external_api.enrich_with_external_data(vrp_input)

        # 3. 최적화
        result = await controller.optimize(vrp_input, strategy, priority)

        # 4. 후처리: 미배정 사유
        if result.get('unassigned'):
            checker = ConstraintChecker(vrp_input)
            reasons_map = checker.analyze_unassigned(result['unassigned'])
            for unassigned in result['unassigned']:
                unassigned['reasons'] = reasons_map[unassigned['id']]

        # 5. 후처리: 품질 분석
        analysis = analyzer.analyze(vrp_input, result)
        statistics = stats_gen.generate(result)

        # 6. 결과 통합
        final_result = {
            **result,
            'analysis': analysis,
            'statistics': statistics,
            '_metadata': {
                'processing_time_ms': int((time.time() - start_time) * 1000),
                'strategy': strategy,
                'priority': priority,
                'used_external_apis': use_external_apis,
                'client': api_key_info['name'],
                'wrapper_version': '2.0',
                'from_cache': False
            }
        }

        # 7. 캐싱
        if use_cache:
            cache_manager.set(vrp_input, final_result)

        return final_result

    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Health check"""
    return {
        "wrapper": "ok",
        "vroom": check_vroom_health(),
        "version": "2.0"
    }

# 실행
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
```

### 5.2 성능 최적화

```python
# 1. 비동기 처리
# 2. 캐싱 (Redis)
# 3. 병렬 처리 (ProcessPoolExecutor)
# 4. 프로파일링 및 병목 제거
```

### 5.3 Docker 배포

```yaml
# docker-compose.yml (최종)

version: '3.8'

services:
  redis:
    image: redis:7-alpine
    container_name: vroom-redis
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data
    networks:
      - routing-network

  osrm:
    image: ghcr.io/project-osrm/osrm-backend:latest
    container_name: osrm-server
    ports:
      - "5000:5000"
    volumes:
      - ./osrm-data:/data
    command: osrm-routed --algorithm mld /data/south-korea-latest.osrm --max-table-size 10000 --port 5000 --ip 0.0.0.0
    restart: unless-stopped
    networks:
      - routing-network

  vroom:
    image: vroom-local:latest
    container_name: vroom-server
    ports:
      - "3000:3000"
    volumes:
      - ./vroom-conf:/conf
    environment:
      - VROOM_ROUTER=osrm
    depends_on:
      - osrm
    restart: unless-stopped
    networks:
      - routing-network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3000/"]
      interval: 30s
      timeout: 5s
      retries: 3

  vroom-wrapper:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: vroom-wrapper-v2
    ports:
      - "8000:8000"
    depends_on:
      - vroom
      - redis
    environment:
      - VROOM_URL=http://vroom:3000
      - REDIS_URL=redis://redis:6379
      - LOG_LEVEL=INFO
      - KAKAO_API_KEY=${KAKAO_API_KEY}
      - WEATHER_API_KEY=${WEATHER_API_KEY}
    volumes:
      - ./logs:/var/log/vroom-wrapper
    networks:
      - routing-network
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 5s
      retries: 3

networks:
  routing-network:
    driver: bridge

volumes:
  redis-data:
```

---

## 기술 스택 및 의존성

### Python 패키지

```txt
# requirements.txt (v2.0)

# Core
fastapi==0.104.1
uvicorn[standard]==0.24.0
pydantic==2.5.0
requests==2.31.0

# Async
httpx==0.25.2
aiofiles==23.2.1

# Data processing
pyyaml==6.0.1
python-dateutil==2.8.2

# Caching
redis==5.0.1

# Rate limiting
slowapi==0.1.9

# Monitoring
prometheus-client==0.19.0

# Testing
pytest==7.4.3
pytest-asyncio==0.21.1
pytest-cov==4.1.0

# Logging
python-json-logger==2.0.7
```

### 외부 서비스

1. **OSRM** (필수)
   - 도로망 라우팅
   - 정적 데이터

2. **VROOM** (필수)
   - VRP 최적화 엔진

3. **Redis** (선택, Phase 4)
   - 결과 캐싱

4. **Kakao API** (선택, Phase 4)
   - 지오코딩
   - 실시간 교통정보

5. **OpenWeatherMap** (선택, Phase 4)
   - 날씨 정보

---

## 테스트 전략

### 단위 테스트 (pytest)

```bash
pytest tests/ -v --cov=. --cov-report=html
```

### 통합 테스트

```python
# tests/test_integration_v2.py

@pytest.mark.asyncio
async def test_full_pipeline_v2():
    """전체 파이프라인 테스트"""
    vrp_input = {
        "vehicles": [{"id": 1, "start": [126.9, 37.5], "capacity": [100]}],
        "jobs": [
            {"id": 1, "location": {"lon": 127.0, "lat": 37.6}, "delivery": 50},
            {"id": 2, "location": [126.8, 37.4], "delivery": 40}
        ]
    }

    business_rules = {
        "vip_priority_boost": True,
        "auto_break_injection": True
    }

    result = await optimize_v2_full(
        vrp_input=vrp_input,
        strategy='single',
        priority='balanced',
        use_cache=False,
        use_external_apis=False,
        business_rules=business_rules
    )

    assert result['code'] == 0
    assert 'analysis' in result
    assert 'statistics' in result
    assert '_metadata' in result
```

### 성능 테스트

```python
# tests/test_performance.py

def test_large_scale():
    """대규모 테스트 (2000 jobs, 250 vehicles)"""
    vrp_input = generate_large_input(2000, 250)

    start = time.time()
    result = optimize_v2_full(vrp_input, strategy='speed')
    duration = time.time() - start

    assert duration < 600  # 10분 이내
    assert len(result.get('unassigned', [])) < 100  # 95% 배정
```

---

## 성능 목표

| 시나리오 | 작업 수 | 차량 수 | 목표 시간 | 배정률 |
|---------|--------|--------|----------|-------|
| 소규모 | 50 | 10 | < 10초 | > 98% |
| 중규모 | 500 | 50 | < 60초 | > 95% |
| 대규모 | 2000 | 250 | < 600초 | > 90% |

---

## 운영 가이드

### 모니터링 (Prometheus + Grafana)

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'vroom-wrapper'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/metrics'
```

### 로깅

```python
# JSON 구조화 로깅
from pythonjsonlogger import jsonlogger

logger = logging.getLogger()
logHandler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter()
logHandler.setFormatter(formatter)
logger.addHandler(logHandler)
```

---

## 마무리

이 마스터 로드맵은:

1. ✅ **모든 문서의 핵심 아이디어 통합**
   - VROOM-WRAPPER-COMPLETE-GUIDE.md (역추적 알고리즘)
   - VROOM-API-CONTROL-GUIDE.md (4가지 제어 레벨)
   - API-DOCUMENTATION.md (완전한 API 레퍼런스)
   - WRAPPER-ARCHITECTURE.md (4계층 아키텍처)

2. ✅ **상세한 구현 코드 제공**
   - Phase별 즉시 사용 가능한 코드
   - 복사 붙여넣기로 구현 가능

3. ✅ **OSRM 한계 명확히**
   - OSRM = 정적 도로망만
   - 실시간 교통/날씨 = 외부 API 필요

4. ✅ **12주 완전한 로드맵**
   - Phase 0-5 상세 일정
   - 주차별 마일스톤
   - 테스트 전략
   - 배포 가이드

**다음 단계**: Phase 1부터 순차 구현 시작! 🚀
