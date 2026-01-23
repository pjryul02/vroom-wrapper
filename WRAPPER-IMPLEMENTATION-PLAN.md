# Wrapper 확장 구현 계획서

## 📋 개요

VROOM Wrapper를 **최대한의 통제력**을 가진 중앙 제어 시스템으로 확장하는 완전한 구현 계획입니다.

**목표**: API 사용자에게 강력하고 유연한 VRP 최적화 플랫폼 제공
- ✅ 현재: 미배정 사유 분석 (v1.0)
- 🎯 목표: 완전한 전처리/제어/후처리/확장 플랫폼 (v2.0)

---

## 🏗️ 전체 아키텍처

```
┌─────────────────────────────────────────────────────────────────┐
│                         External API Users                       │
│                   (Python/JS/Mobile clients)                    │
└──────────────────────────────────┬──────────────────────────────┘
                                   │ HTTP/WebSocket
                                   ▼
┌─────────────────────────────────────────────────────────────────┐
│                    VROOM Wrapper v2.0 (FastAPI)                 │
├─────────────────────────────────────────────────────────────────┤
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ 1. Pre-Processing Layer                                   │ │
│  │  • InputValidator: 입력 검증                              │ │
│  │  • InputNormalizer: 좌표/시간 정규화                      │ │
│  │  • BusinessRuleEngine: 비즈니스 로직 적용                 │ │
│  │  • ConstraintTransformer: 제약조건 변환                   │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                   │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ 2. Control Layer                                          │ │
│  │  • VROOMConfigManager: VROOM 설정 동적 제어               │ │
│  │  • OptimizationController: 최적화 전략 선택               │ │
│  │  • ConstraintTuner: 제약조건 자동 조정                    │ │
│  │  • MultiScenarioEngine: 다중 시나리오 최적화              │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                   │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ 3. Post-Processing Layer                                  │ │
│  │  • ConstraintChecker: 미배정 사유 분석 (기존)             │ │
│  │  • ResultAnalyzer: 결과 품질 분석                         │ │
│  │  • StatisticsGenerator: 통계 생성                         │ │
│  │  • CostCalculator: 비용/탄소 계산                         │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                   │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ 4. Extension Layer                                        │ │
│  │  • ExternalAPIIntegrator: 외부 API 연동                   │ │
│  │  • CacheManager: 결과 캐싱                                │ │
│  │  • RateLimiter: API 제한                                  │ │
│  │  • MonitoringCollector: 모니터링 수집                     │ │
│  └───────────────────────────────────────────────────────────┘ │
└─────────────────────────────────┬───────────────────────────────┘
                                   │ Subprocess call
                                   ▼
┌─────────────────────────────────────────────────────────────────┐
│                    VROOM Engine (Docker)                        │
│                  + Custom config.yml control                    │
└─────────────────────────────────┬───────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────┐
│                    OSRM Engine (Docker)                         │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📦 Phase 1: 입력 전처리 강화 (1-2주)

### 1.1 InputValidator

**목적**: 입력 데이터 완전성 검증

```python
# vroom_wrapper.py에 추가

from typing import Dict, List, Any, Optional
from pydantic import BaseModel, validator, Field
import re

class LocationModel(BaseModel):
    """좌표 모델"""
    lon: float = Field(..., ge=-180, le=180)
    lat: float = Field(..., ge=-90, le=90)

    @validator('lon', 'lat')
    def check_korea_bounds(cls, v, values, field):
        """한국 영역 체크 (선택적)"""
        if field.name == 'lon' and not (124 <= v <= 132):
            raise ValueError('Longitude must be in Korea bounds (124-132)')
        if field.name == 'lat' and not (33 <= v <= 43):
            raise ValueError('Latitude must be in Korea bounds (33-43)')
        return v

class TimeWindowModel(BaseModel):
    """시간창 모델"""
    start: int = Field(..., ge=0)
    end: int = Field(..., ge=0)

    @validator('end')
    def end_after_start(cls, v, values):
        if 'start' in values and v <= values['start']:
            raise ValueError('End time must be after start time')
        return v

class JobModel(BaseModel):
    """작업 모델"""
    id: int
    location: List[float]  # [lon, lat]
    service: Optional[int] = 0
    delivery: Optional[List[int]] = None
    pickup: Optional[List[int]] = None
    skills: Optional[List[int]] = None
    priority: Optional[int] = 0
    time_windows: Optional[List[List[int]]] = None

    @validator('location')
    def validate_location(cls, v):
        if len(v) != 2:
            raise ValueError('Location must be [lon, lat]')
        LocationModel(lon=v[0], lat=v[1])  # 검증
        return v

    @validator('time_windows')
    def validate_time_windows(cls, v):
        if v:
            for tw in v:
                if len(tw) != 2:
                    raise ValueError('Time window must be [start, end]')
                TimeWindowModel(start=tw[0], end=tw[1])
        return v

class VehicleModel(BaseModel):
    """차량 모델"""
    id: int
    start: List[float]
    end: Optional[List[float]] = None
    capacity: Optional[List[int]] = None
    skills: Optional[List[int]] = None
    time_window: Optional[List[int]] = None
    max_tasks: Optional[int] = None

    @validator('start', 'end')
    def validate_location(cls, v):
        if v and len(v) != 2:
            raise ValueError('Location must be [lon, lat]')
        if v:
            LocationModel(lon=v[0], lat=v[1])
        return v

class VRPInputModel(BaseModel):
    """VRP 입력 전체 모델"""
    vehicles: List[VehicleModel]
    jobs: List[JobModel]
    shipments: Optional[List[Dict]] = []

    @validator('vehicles')
    def at_least_one_vehicle(cls, v):
        if not v:
            raise ValueError('At least one vehicle required')
        return v

    @validator('jobs')
    def at_least_one_job(cls, v):
        if not v:
            raise ValueError('At least one job required')
        return v

# FastAPI 엔드포인트에 적용
@app.post("/optimize")
async def optimize_with_validation(vrp_input: VRPInputModel):
    """검증된 입력으로 최적화"""
    # Pydantic이 자동으로 검증
    vrp_dict = vrp_input.dict()

    # 기존 로직 실행
    return await optimize_with_reasons(vrp_dict)
```

### 1.2 InputNormalizer

**목적**: 다양한 입력 형식을 VROOM 표준으로 변환

```python
class InputNormalizer:
    """입력 정규화"""

    def normalize(self, vrp_input: Dict[str, Any]) -> Dict[str, Any]:
        """전체 정규화 파이프라인"""
        vrp_input = self._normalize_coordinates(vrp_input)
        vrp_input = self._normalize_time_format(vrp_input)
        vrp_input = self._add_missing_defaults(vrp_input)
        vrp_input = self._normalize_capacity_format(vrp_input)
        return vrp_input

    def _normalize_coordinates(self, vrp_input: Dict) -> Dict:
        """
        다양한 좌표 형식 지원:
        - [lon, lat] (VROOM 표준)
        - {"lon": x, "lat": y}
        - {"longitude": x, "latitude": y}
        - "address string" -> geocoding
        """
        for job in vrp_input.get('jobs', []):
            job['location'] = self._to_lon_lat(job['location'])

        for vehicle in vrp_input.get('vehicles', []):
            vehicle['start'] = self._to_lon_lat(vehicle['start'])
            if 'end' in vehicle:
                vehicle['end'] = self._to_lon_lat(vehicle['end'])

        return vrp_input

    def _to_lon_lat(self, location: Any) -> List[float]:
        """다양한 좌표 형식을 [lon, lat]로 변환"""
        if isinstance(location, list):
            return location  # 이미 표준 형식

        if isinstance(location, dict):
            # {"lon": x, "lat": y} 형식
            if 'lon' in location and 'lat' in location:
                return [location['lon'], location['lat']]
            # {"longitude": x, "latitude": y} 형식
            if 'longitude' in location and 'latitude' in location:
                return [location['longitude'], location['latitude']]

        if isinstance(location, str):
            # 주소 문자열 -> geocoding 필요
            return self._geocode_address(location)

        raise ValueError(f"Unsupported location format: {location}")

    def _geocode_address(self, address: str) -> List[float]:
        """주소 -> 좌표 변환 (Kakao/Naver API 사용)"""
        # TODO: Implement geocoding
        raise NotImplementedError("Geocoding not implemented yet")

    def _normalize_time_format(self, vrp_input: Dict) -> Dict:
        """
        시간 형식 정규화:
        - Unix timestamp (seconds) -> VROOM seconds
        - ISO 8601 string -> VROOM seconds
        - "HH:MM" -> seconds from day start
        """
        for job in vrp_input.get('jobs', []):
            if 'time_windows' in job:
                job['time_windows'] = [
                    [self._to_seconds(tw[0]), self._to_seconds(tw[1])]
                    for tw in job['time_windows']
                ]

        for vehicle in vrp_input.get('vehicles', []):
            if 'time_window' in vehicle:
                tw = vehicle['time_window']
                vehicle['time_window'] = [
                    self._to_seconds(tw[0]),
                    self._to_seconds(tw[1])
                ]

        return vrp_input

    def _to_seconds(self, time_value: Any) -> int:
        """다양한 시간 형식을 초(seconds)로 변환"""
        if isinstance(time_value, int):
            return time_value  # 이미 초 단위

        if isinstance(time_value, str):
            # "09:30" 형식
            if ':' in time_value:
                h, m = map(int, time_value.split(':'))
                return h * 3600 + m * 60

            # ISO 8601 형식 (예: "2024-01-23T09:30:00")
            from datetime import datetime
            dt = datetime.fromisoformat(time_value)
            # 하루 시작부터의 초
            return dt.hour * 3600 + dt.minute * 60 + dt.second

        raise ValueError(f"Unsupported time format: {time_value}")

    def _add_missing_defaults(self, vrp_input: Dict) -> Dict:
        """누락된 필드에 기본값 추가"""
        for job in vrp_input.get('jobs', []):
            job.setdefault('service', 300)  # 기본 5분
            job.setdefault('priority', 0)

        for vehicle in vrp_input.get('vehicles', []):
            vehicle.setdefault('capacity', [1000])  # 기본 용량
            if 'end' not in vehicle:
                vehicle['end'] = vehicle['start']  # 출발지로 복귀

        return vrp_input

    def _normalize_capacity_format(self, vrp_input: Dict) -> Dict:
        """용량 형식 정규화 (단일 값 -> 리스트)"""
        for vehicle in vrp_input.get('vehicles', []):
            if 'capacity' in vehicle:
                cap = vehicle['capacity']
                if isinstance(cap, int):
                    vehicle['capacity'] = [cap]  # 단일 값 -> 리스트

        for job in vrp_input.get('jobs', []):
            for key in ['delivery', 'pickup']:
                if key in job:
                    val = job[key]
                    if isinstance(val, int):
                        job[key] = [val]

        return vrp_input
```

### 1.3 BusinessRuleEngine

**목적**: 비즈니스 규칙을 VROOM 제약조건으로 변환

```python
class BusinessRuleEngine:
    """비즈니스 규칙 엔진"""

    def apply_rules(self, vrp_input: Dict[str, Any], rules: Dict[str, Any]) -> Dict[str, Any]:
        """비즈니스 규칙 적용"""
        if rules.get('vip_priority_boost'):
            vrp_input = self._boost_vip_priority(vrp_input)

        if rules.get('urgent_time_preference'):
            vrp_input = self._prefer_urgent_time(vrp_input)

        if rules.get('zone_restrictions'):
            vrp_input = self._apply_zone_restrictions(vrp_input, rules['zone_restrictions'])

        if rules.get('driver_specialization'):
            vrp_input = self._apply_driver_skills(vrp_input, rules['driver_specialization'])

        if rules.get('auto_break_injection'):
            vrp_input = self._inject_breaks(vrp_input)

        return vrp_input

    def _boost_vip_priority(self, vrp_input: Dict) -> Dict:
        """VIP 고객 우선순위 자동 증가"""
        for job in vrp_input.get('jobs', []):
            if job.get('customer_type') == 'VIP':
                job['priority'] = job.get('priority', 0) + 100
        return vrp_input

    def _prefer_urgent_time(self, vrp_input: Dict) -> Dict:
        """긴급 주문 시간창 우선 배정"""
        current_time = 32400  # 예: 09:00

        for job in vrp_input.get('jobs', []):
            if job.get('is_urgent'):
                # 2시간 이내 배송 시간창 생성
                job['time_windows'] = [[current_time, current_time + 7200]]
                job['priority'] = job.get('priority', 0) + 50

        return vrp_input

    def _apply_zone_restrictions(self, vrp_input: Dict, zones: Dict) -> Dict:
        """지역별 제약 적용 (예: 강남은 차량 1,2만)"""
        # zones = {"gangnam": {"bounds": [lon_min, lat_min, lon_max, lat_max], "vehicle_ids": [1, 2]}}

        for zone_name, zone_config in zones.items():
            bounds = zone_config['bounds']
            allowed_vehicles = zone_config['vehicle_ids']

            # 해당 지역의 작업에 skills 할당
            zone_skill = hash(zone_name) % 10000  # 지역별 고유 skill ID

            for job in vrp_input.get('jobs', []):
                lon, lat = job['location']
                if self._in_bounds(lon, lat, bounds):
                    job.setdefault('skills', []).append(zone_skill)

            # 허용된 차량에만 해당 skill 부여
            for vehicle in vrp_input.get('vehicles', []):
                if vehicle['id'] in allowed_vehicles:
                    vehicle.setdefault('skills', []).append(zone_skill)

        return vrp_input

    def _in_bounds(self, lon: float, lat: float, bounds: List[float]) -> bool:
        """좌표가 경계 내에 있는지 확인"""
        lon_min, lat_min, lon_max, lat_max = bounds
        return lon_min <= lon <= lon_max and lat_min <= lat <= lat_max

    def _apply_driver_skills(self, vrp_input: Dict, specializations: Dict) -> Dict:
        """기사 특수 능력 적용"""
        # specializations = {"refrigerated": {"vehicle_ids": [1, 3], "job_types": ["frozen", "cold"]}}

        for spec_name, spec_config in specializations.items():
            spec_skill = hash(spec_name) % 10000

            # 특수 차량에 skill 부여
            for vehicle in vrp_input.get('vehicles', []):
                if vehicle['id'] in spec_config['vehicle_ids']:
                    vehicle.setdefault('skills', []).append(spec_skill)

            # 해당 타입 작업에 skill 요구
            for job in vrp_input.get('jobs', []):
                if job.get('product_type') in spec_config['job_types']:
                    job.setdefault('skills', []).append(spec_skill)

        return vrp_input

    def _inject_breaks(self, vrp_input: Dict) -> Dict:
        """차량에 휴식시간 자동 삽입"""
        for vehicle in vrp_input.get('vehicles', []):
            if 'breaks' not in vehicle:
                # 점심시간 자동 추가 (12:00-13:00)
                vehicle['breaks'] = [{
                    'id': vehicle['id'] * 1000,
                    'time_windows': [[43200, 46800]],  # 12:00-13:00
                    'service': 3600,  # 1시간
                    'description': '점심시간'
                }]

        return vrp_input
```

---

## 🎛️ Phase 2: VROOM 통제 강화 (2-3주)

### 2.1 VROOMConfigManager

**목적**: VROOM 설정을 동적으로 제어

```python
import yaml
from pathlib import Path

class VROOMConfigManager:
    """VROOM 설정 동적 관리"""

    CONFIG_PATH = Path("/home/shawn/vroom-conf/config.yml")

    def __init__(self):
        self.default_config = self._load_config()

    def _load_config(self) -> Dict:
        """현재 설정 로드"""
        with open(self.CONFIG_PATH) as f:
            return yaml.safe_load(f)

    def _save_config(self, config: Dict):
        """설정 저장 및 VROOM 재시작"""
        with open(self.CONFIG_PATH, 'w') as f:
            yaml.dump(config, f)

        # VROOM 컨테이너 재시작
        import subprocess
        subprocess.run(['docker-compose', 'restart', 'vroom'],
                      cwd='/home/shawn/vroom-wrapper-project')

    def optimize_for_scenario(self, num_jobs: int, num_vehicles: int,
                             priority: str = 'balanced') -> Dict:
        """
        시나리오에 맞는 최적 설정 선택

        priority:
        - 'speed': 빠른 결과 우선
        - 'quality': 최고 품질 우선
        - 'balanced': 균형
        """
        config = self.default_config.copy()
        cli_args = config['cliArgs']

        # 작업 규모에 따른 조정
        if num_jobs < 50:
            # 소규모: 최고 품질
            cli_args['explore'] = 5
            cli_args['threads'] = 4
            cli_args['timeout'] = 120000  # 2분
        elif num_jobs < 500:
            # 중규모: 균형
            cli_args['explore'] = 4
            cli_args['threads'] = 6
            cli_args['timeout'] = 300000  # 5분
        else:
            # 대규모: 속도 우선
            cli_args['explore'] = 2
            cli_args['threads'] = 8
            cli_args['timeout'] = 600000  # 10분

        # 우선순위 오버라이드
        if priority == 'speed':
            cli_args['explore'] = max(1, cli_args['explore'] - 2)
            cli_args['timeout'] = cli_args['timeout'] // 2
        elif priority == 'quality':
            cli_args['explore'] = 5
            cli_args['timeout'] = cli_args['timeout'] * 2

        return cli_args

    def apply_temporary_config(self, **kwargs):
        """임시 설정 적용 (재시작 없이)"""
        # VROOM CLI args로 전달
        return kwargs

# 사용 예시
config_manager = VROOMConfigManager()

@app.post("/optimize")
async def optimize_with_config(
    vrp_input: Dict[str, Any],
    priority: str = 'balanced'
):
    """동적 설정으로 최적화"""
    num_jobs = len(vrp_input.get('jobs', []))
    num_vehicles = len(vrp_input.get('vehicles', []))

    # 최적 설정 선택
    optimal_config = config_manager.optimize_for_scenario(
        num_jobs, num_vehicles, priority
    )

    # VROOM 호출 시 config 전달
    result = call_vroom_with_config(vrp_input, optimal_config)
    return result
```

### 2.2 ConstraintTuner

**목적**: 제약조건 자동 조정으로 미배정 최소화

```python
class ConstraintTuner:
    """제약조건 자동 튜닝"""

    def auto_tune(self, vrp_input: Dict, initial_result: Dict) -> Dict:
        """
        미배정이 많으면 제약을 완화하여 재시도

        전략:
        1. Time window 확장
        2. Capacity 증가
        3. Skills 완화
        4. Max tasks 증가
        """
        unassigned = initial_result.get('unassigned', [])

        if not unassigned:
            return initial_result  # 이미 완벽

        # 미배정 사유 분석
        reasons = self._analyze_unassigned_reasons(vrp_input, unassigned)

        # 사유별 조정 전략
        if reasons.get('time_window_violations', 0) > len(unassigned) * 0.5:
            vrp_input = self._relax_time_windows(vrp_input)

        if reasons.get('capacity_violations', 0) > len(unassigned) * 0.3:
            vrp_input = self._increase_capacity(vrp_input)

        if reasons.get('skill_violations', 0) > len(unassigned) * 0.4:
            vrp_input = self._relax_skills(vrp_input)

        # 재최적화
        return call_vroom(vrp_input)

    def _analyze_unassigned_reasons(self, vrp_input: Dict, unassigned: List) -> Dict:
        """미배정 사유 통계"""
        checker = ConstraintChecker(vrp_input)
        reasons_count = {
            'time_window_violations': 0,
            'capacity_violations': 0,
            'skill_violations': 0,
            'max_tasks_violations': 0
        }

        for u in unassigned:
            job_reasons = checker._check_job_violations(
                checker.jobs_by_id[u['id']]
            )
            for reason in job_reasons:
                if 'time window' in reason['reason'].lower():
                    reasons_count['time_window_violations'] += 1
                elif 'capacity' in reason['reason'].lower():
                    reasons_count['capacity_violations'] += 1
                elif 'skill' in reason['reason'].lower():
                    reasons_count['skill_violations'] += 1
                elif 'max tasks' in reason['reason'].lower():
                    reasons_count['max_tasks_violations'] += 1

        return reasons_count

    def _relax_time_windows(self, vrp_input: Dict, extend_by: int = 3600) -> Dict:
        """시간창 확장 (+1시간)"""
        for job in vrp_input.get('jobs', []):
            if 'time_windows' in job:
                job['time_windows'] = [
                    [tw[0] - extend_by, tw[1] + extend_by]
                    for tw in job['time_windows']
                ]
        return vrp_input

    def _increase_capacity(self, vrp_input: Dict, factor: float = 1.2) -> Dict:
        """차량 용량 20% 증가"""
        for vehicle in vrp_input.get('vehicles', []):
            if 'capacity' in vehicle:
                vehicle['capacity'] = [
                    int(cap * factor) for cap in vehicle['capacity']
                ]
        return vrp_input

    def _relax_skills(self, vrp_input: Dict) -> Dict:
        """Skills 요구사항 완화 (일부 제거)"""
        for job in vrp_input.get('jobs', []):
            if 'skills' in job and len(job['skills']) > 1:
                # 가장 제한적인 skill 하나만 남김
                job['skills'] = job['skills'][:1]
        return vrp_input
```

### 2.3 MultiScenarioEngine

**목적**: 여러 시나리오를 병렬 실행하여 최적 선택

```python
import asyncio
from concurrent.futures import ProcessPoolExecutor

class MultiScenarioEngine:
    """다중 시나리오 최적화 엔진"""

    def __init__(self, max_workers: int = 4):
        self.executor = ProcessPoolExecutor(max_workers=max_workers)

    async def optimize_multi_scenario(self, vrp_input: Dict) -> Dict:
        """
        여러 시나리오를 병렬 실행하여 최고 결과 선택

        시나리오:
        1. Speed-focused (explore=1)
        2. Balanced (explore=3)
        3. Quality-focused (explore=5)
        4. Time-relaxed (시간창 +30분)
        """
        scenarios = [
            {'name': 'speed', 'explore': 1, 'timeout': 30000},
            {'name': 'balanced', 'explore': 3, 'timeout': 60000},
            {'name': 'quality', 'explore': 5, 'timeout': 120000},
            {'name': 'time_relaxed', 'explore': 3, 'timeout': 60000,
             'time_window_extend': 1800},
        ]

        # 병렬 실행
        tasks = []
        for scenario in scenarios:
            modified_input = self._apply_scenario(vrp_input.copy(), scenario)
            task = self._run_scenario_async(modified_input, scenario)
            tasks.append(task)

        # 모든 시나리오 완료 대기
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 최적 결과 선택
        best_result = self._select_best_result(results)
        return best_result

    def _apply_scenario(self, vrp_input: Dict, scenario: Dict) -> Dict:
        """시나리오별 입력 수정"""
        if scenario.get('time_window_extend'):
            extend = scenario['time_window_extend']
            for job in vrp_input.get('jobs', []):
                if 'time_windows' in job:
                    job['time_windows'] = [
                        [tw[0] - extend, tw[1] + extend]
                        for tw in job['time_windows']
                    ]
        return vrp_input

    async def _run_scenario_async(self, vrp_input: Dict, scenario: Dict) -> Dict:
        """시나리오 비동기 실행"""
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            self.executor,
            call_vroom_with_config,
            vrp_input,
            scenario
        )
        result['scenario_name'] = scenario['name']
        return result

    def _select_best_result(self, results: List[Dict]) -> Dict:
        """
        최적 결과 선택 기준:
        1. 미배정 수 (적을수록 좋음)
        2. 총 거리 (짧을수록 좋음)
        3. 총 시간 (짧을수록 좋음)
        """
        valid_results = [r for r in results if not isinstance(r, Exception)]

        if not valid_results:
            raise RuntimeError("All scenarios failed")

        # 점수 계산
        scored_results = []
        for result in valid_results:
            score = self._calculate_score(result)
            scored_results.append((score, result))

        # 최고 점수 반환
        scored_results.sort(key=lambda x: x[0], reverse=True)
        best_result = scored_results[0][1]

        # 메타데이터 추가
        best_result['all_scenarios'] = [
            {
                'scenario': r['scenario_name'],
                'unassigned': len(r.get('unassigned', [])),
                'distance': r.get('summary', {}).get('distance', 0),
                'score': s
            }
            for s, r in scored_results
        ]

        return best_result

    def _calculate_score(self, result: Dict) -> float:
        """결과 점수 계산 (0-100)"""
        unassigned_count = len(result.get('unassigned', []))
        total_distance = result.get('summary', {}).get('distance', 0)
        total_duration = result.get('summary', {}).get('duration', 0)

        # 가중치 적용
        unassigned_penalty = unassigned_count * 10  # 미배정 1개당 -10점
        distance_score = max(0, 100 - total_distance / 1000)  # 거리 기반
        duration_score = max(0, 100 - total_duration / 3600)  # 시간 기반

        score = (distance_score * 0.4 + duration_score * 0.4
                 - unassigned_penalty * 0.2)

        return max(0, min(100, score))
```

---

## 📊 Phase 3: 후처리 강화 (1-2주)

### 3.1 ResultAnalyzer (확장)

**목적**: 결과 품질 심층 분석

```python
class ResultAnalyzer:
    """결과 분석기 (확장)"""

    def analyze(self, vrp_input: Dict, result: Dict) -> Dict:
        """종합 분석"""
        analysis = {
            'quality_score': self._calculate_quality_score(result),
            'efficiency_metrics': self._calculate_efficiency(result),
            'distribution_stats': self._analyze_distribution(result),
            'recommendations': self._generate_recommendations(vrp_input, result),
            'cost_breakdown': self._calculate_costs(result),
        }
        return analysis

    def _calculate_quality_score(self, result: Dict) -> Dict:
        """품질 점수 (0-100)"""
        total_jobs = len(result.get('routes', [])) + len(result.get('unassigned', []))
        unassigned_count = len(result.get('unassigned', []))

        # 기본 점수
        assignment_rate = (total_jobs - unassigned_count) / total_jobs if total_jobs > 0 else 0
        base_score = assignment_rate * 100

        # 효율성 보너스
        avg_distance_per_job = result.get('summary', {}).get('distance', 0) / max(1, total_jobs)
        if avg_distance_per_job < 5000:  # 5km 이하
            base_score += 10

        # 균형 보너스 (차량 간 작업 수 균형)
        routes = result.get('routes', [])
        if routes:
            job_counts = [len(r.get('steps', [])) - 2 for r in routes]  # start/end 제외
            std_dev = self._std_deviation(job_counts)
            if std_dev < 2:  # 표준편차 2 이하
                base_score += 5

        return {
            'score': min(100, base_score),
            'assignment_rate': assignment_rate * 100,
            'efficiency_bonus': min(10, base_score - assignment_rate * 100)
        }

    def _calculate_efficiency(self, result: Dict) -> Dict:
        """효율성 지표"""
        summary = result.get('summary', {})
        routes = result.get('routes', [])

        total_distance = summary.get('distance', 0)
        total_duration = summary.get('duration', 0)
        total_jobs = sum(len(r.get('steps', [])) - 2 for r in routes)

        return {
            'avg_distance_per_job': total_distance / max(1, total_jobs),
            'avg_duration_per_job': total_duration / max(1, total_jobs),
            'total_distance_km': total_distance / 1000,
            'total_duration_hours': total_duration / 3600,
            'vehicle_utilization': len([r for r in routes if len(r.get('steps', [])) > 2]) / len(routes) * 100
        }

    def _analyze_distribution(self, result: Dict) -> Dict:
        """작업 분배 분석"""
        routes = result.get('routes', [])

        vehicle_loads = []
        vehicle_distances = []
        vehicle_job_counts = []

        for route in routes:
            steps = route.get('steps', [])
            job_count = len(steps) - 2  # start/end 제외
            distance = route.get('distance', 0)

            vehicle_job_counts.append(job_count)
            vehicle_distances.append(distance)

        return {
            'jobs_per_vehicle': {
                'min': min(vehicle_job_counts) if vehicle_job_counts else 0,
                'max': max(vehicle_job_counts) if vehicle_job_counts else 0,
                'avg': sum(vehicle_job_counts) / len(vehicle_job_counts) if vehicle_job_counts else 0,
                'std_dev': self._std_deviation(vehicle_job_counts)
            },
            'distance_per_vehicle': {
                'min': min(vehicle_distances) if vehicle_distances else 0,
                'max': max(vehicle_distances) if vehicle_distances else 0,
                'avg': sum(vehicle_distances) / len(vehicle_distances) if vehicle_distances else 0
            }
        }

    def _generate_recommendations(self, vrp_input: Dict, result: Dict) -> List[str]:
        """개선 제안"""
        recommendations = []

        unassigned = result.get('unassigned', [])
        if len(unassigned) > 0:
            recommendations.append(f"{len(unassigned)}개 미배정 작업 있음. 차량 추가 또는 제약조건 완화 권장.")

        routes = result.get('routes', [])
        empty_routes = [r for r in routes if len(r.get('steps', [])) <= 2]
        if len(empty_routes) > 0:
            recommendations.append(f"{len(empty_routes)}대 차량이 미사용. 차량 수 감소 고려.")

        # 작업 불균형 체크
        job_counts = [len(r.get('steps', [])) - 2 for r in routes]
        if job_counts and max(job_counts) > min(job_counts) * 2:
            recommendations.append("차량 간 작업 불균형 심함. 시간창 조정 또는 skills 재검토 권장.")

        return recommendations

    def _calculate_costs(self, result: Dict) -> Dict:
        """비용 계산"""
        summary = result.get('summary', {})
        total_distance = summary.get('distance', 0) / 1000  # km
        total_duration = summary.get('duration', 0) / 3600  # hours

        # 가정: 유류비 1500원/km, 인건비 15000원/시간
        fuel_cost = total_distance * 1500
        labor_cost = total_duration * 15000
        total_cost = fuel_cost + labor_cost

        # 탄소 배출 (가정: 0.2kg CO2/km)
        carbon_footprint = total_distance * 0.2

        return {
            'fuel_cost_krw': round(fuel_cost),
            'labor_cost_krw': round(labor_cost),
            'total_cost_krw': round(total_cost),
            'carbon_footprint_kg': round(carbon_footprint, 2)
        }

    def _std_deviation(self, values: List[float]) -> float:
        """표준편차 계산"""
        if not values:
            return 0
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        return variance ** 0.5
```

### 3.2 StatisticsGenerator

```python
class StatisticsGenerator:
    """통계 생성기"""

    def generate(self, result: Dict) -> Dict:
        """전체 통계 생성"""
        return {
            'vehicle_statistics': self._vehicle_stats(result),
            'time_statistics': self._time_stats(result),
            'location_statistics': self._location_stats(result),
            'skill_statistics': self._skill_stats(result)
        }

    def _vehicle_stats(self, result: Dict) -> List[Dict]:
        """차량별 상세 통계"""
        stats = []
        for route in result.get('routes', []):
            vehicle_id = route.get('vehicle')
            steps = route.get('steps', [])

            job_steps = [s for s in steps if s['type'] == 'job']

            stats.append({
                'vehicle_id': vehicle_id,
                'total_jobs': len(job_steps),
                'total_distance_km': route.get('distance', 0) / 1000,
                'total_duration_hours': route.get('duration', 0) / 3600,
                'service_time_hours': route.get('service', 0) / 3600,
                'waiting_time_hours': route.get('waiting_time', 0) / 3600,
                'first_job_time': steps[1]['arrival'] if len(steps) > 1 else None,
                'last_job_time': steps[-2]['arrival'] if len(steps) > 2 else None
            })

        return stats

    def _time_stats(self, result: Dict) -> Dict:
        """시간대별 통계"""
        time_slots = {}  # {hour: job_count}

        for route in result.get('routes', []):
            for step in route.get('steps', []):
                if step['type'] == 'job':
                    arrival = step.get('arrival', 0)
                    hour = (arrival // 3600) % 24
                    time_slots[hour] = time_slots.get(hour, 0) + 1

        return {
            'busiest_hour': max(time_slots, key=time_slots.get) if time_slots else None,
            'hourly_distribution': time_slots
        }

    def _location_stats(self, result: Dict) -> Dict:
        """지역별 통계 (간단한 그리드 기반)"""
        # TODO: 실제로는 행정구역 API 사용
        return {'note': 'Location-based statistics not implemented yet'}

    def _skill_stats(self, result: Dict) -> Dict:
        """스킬별 통계"""
        # TODO: 입력 데이터와 결합 필요
        return {'note': 'Skill-based statistics require input data'}
```

---

## 🔌 Phase 4: 확장 기능 (2-3주)

### 4.1 ExternalAPIIntegrator

```python
import httpx
from typing import Optional

class ExternalAPIIntegrator:
    """외부 API 연동"""

    def __init__(self):
        self.kakao_api_key = "YOUR_KAKAO_API_KEY"
        self.weather_api_key = "YOUR_WEATHER_API_KEY"

    async def enrich_with_external_data(self, vrp_input: Dict) -> Dict:
        """외부 데이터로 입력 강화"""
        # 날씨 정보 추가
        vrp_input = await self._add_weather_info(vrp_input)

        # 실시간 교통 정보 반영
        vrp_input = await self._adjust_for_traffic(vrp_input)

        # 주소 -> 좌표 변환
        vrp_input = await self._geocode_addresses(vrp_input)

        return vrp_input

    async def _add_weather_info(self, vrp_input: Dict) -> Dict:
        """날씨 정보 추가 (악천후 시 서비스 시간 증가)"""
        async with httpx.AsyncClient() as client:
            # OpenWeatherMap API 호출 (예시)
            response = await client.get(
                "https://api.openweathermap.org/data/2.5/weather",
                params={
                    'lat': 37.5665,
                    'lon': 126.9780,
                    'appid': self.weather_api_key
                }
            )
            weather = response.json()

        # 비/눈이면 서비스 시간 20% 증가
        if weather.get('weather', [{}])[0].get('main') in ['Rain', 'Snow']:
            for job in vrp_input.get('jobs', []):
                job['service'] = int(job.get('service', 300) * 1.2)

        return vrp_input

    async def _adjust_for_traffic(self, vrp_input: Dict) -> Dict:
        """실시간 교통 정보 반영"""
        # TODO: Google/Kakao Traffic API 연동
        # 혼잡도가 높은 지역의 작업은 시간창 조정
        return vrp_input

    async def _geocode_addresses(self, vrp_input: Dict) -> Dict:
        """주소 -> 좌표 변환 (Kakao Local API)"""
        async with httpx.AsyncClient() as client:
            for job in vrp_input.get('jobs', []):
                if 'address' in job and 'location' not in job:
                    response = await client.get(
                        "https://dapi.kakao.com/v2/local/search/address.json",
                        headers={'Authorization': f'KakaoAK {self.kakao_api_key}'},
                        params={'query': job['address']}
                    )
                    result = response.json()

                    if result.get('documents'):
                        doc = result['documents'][0]
                        job['location'] = [float(doc['x']), float(doc['y'])]

        return vrp_input
```

### 4.2 CacheManager

```python
import redis
import json
import hashlib

class CacheManager:
    """결과 캐싱"""

    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis = redis.from_url(redis_url)
        self.ttl = 3600  # 1시간

    def get(self, vrp_input: Dict) -> Optional[Dict]:
        """캐시에서 결과 조회"""
        cache_key = self._generate_key(vrp_input)
        cached = self.redis.get(cache_key)

        if cached:
            return json.loads(cached)
        return None

    def set(self, vrp_input: Dict, result: Dict):
        """결과 캐싱"""
        cache_key = self._generate_key(vrp_input)
        self.redis.setex(
            cache_key,
            self.ttl,
            json.dumps(result)
        )

    def _generate_key(self, vrp_input: Dict) -> str:
        """입력 해시 생성 (캐시 키)"""
        # 입력을 정규화하여 해시
        normalized = json.dumps(vrp_input, sort_keys=True)
        return hashlib.sha256(normalized.encode()).hexdigest()
```

### 4.3 RateLimiter & Authentication

```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Header, HTTPException

# Rate Limiter 설정
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# API Key 관리
API_KEYS = {
    "client1-key-abc123": {"name": "Client 1", "rate_limit": "100/hour"},
    "client2-key-xyz789": {"name": "Client 2", "rate_limit": "50/hour"}
}

def verify_api_key(x_api_key: str = Header(None)) -> dict:
    """API Key 검증"""
    if x_api_key not in API_KEYS:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return API_KEYS[x_api_key]

# 보호된 엔드포인트
@app.post("/optimize")
@limiter.limit("100/hour")
async def optimize_protected(
    request: Request,
    vrp_input: Dict[str, Any],
    api_key_info: dict = Depends(verify_api_key)
):
    """API Key 및 Rate Limit 적용"""
    logger.info(f"Request from {api_key_info['name']}")

    # 기존 로직
    return await optimize_with_reasons(vrp_input)
```

---

## 🚀 통합 파이프라인

모든 컴포넌트를 통합한 최종 엔드포인트:

```python
@app.post("/optimize/v2")
@limiter.limit("100/hour")
async def optimize_v2(
    request: Request,
    vrp_input: VRPInputModel,
    priority: str = 'balanced',
    use_cache: bool = True,
    use_multi_scenario: bool = False,
    enrich_external: bool = False,
    auto_tune: bool = True,
    api_key_info: dict = Depends(verify_api_key)
):
    """
    완전한 v2.0 최적화 파이프라인

    Parameters:
    - priority: 'speed' | 'balanced' | 'quality'
    - use_cache: 캐시 사용 여부
    - use_multi_scenario: 다중 시나리오 실행
    - enrich_external: 외부 API 데이터 추가
    - auto_tune: 자동 제약조건 튜닝
    """
    start_time = time.time()

    # 0. 입력 검증 (Pydantic이 자동 처리)
    vrp_dict = vrp_input.dict()

    # 1. 캐시 확인
    if use_cache:
        cache_manager = CacheManager()
        cached_result = cache_manager.get(vrp_dict)
        if cached_result:
            logger.info("Cache hit")
            return cached_result

    # 2. 전처리
    normalizer = InputNormalizer()
    vrp_dict = normalizer.normalize(vrp_dict)

    business_rules = BusinessRuleEngine()
    vrp_dict = business_rules.apply_rules(vrp_dict, {
        'vip_priority_boost': True,
        'auto_break_injection': True
    })

    # 3. 외부 데이터 연동 (옵션)
    if enrich_external:
        external_api = ExternalAPIIntegrator()
        vrp_dict = await external_api.enrich_with_external_data(vrp_dict)

    # 4. 최적화 실행
    if use_multi_scenario:
        # 다중 시나리오
        multi_engine = MultiScenarioEngine()
        result = await multi_engine.optimize_multi_scenario(vrp_dict)
    else:
        # 단일 최적화
        config_manager = VROOMConfigManager()
        optimal_config = config_manager.optimize_for_scenario(
            len(vrp_dict['jobs']),
            len(vrp_dict['vehicles']),
            priority
        )
        result = call_vroom_with_config(vrp_dict, optimal_config)

    # 5. 자동 튜닝 (옵션)
    if auto_tune and len(result.get('unassigned', [])) > 0:
        tuner = ConstraintTuner()
        result = tuner.auto_tune(vrp_dict, result)

    # 6. 후처리
    checker = ConstraintChecker(vrp_dict)
    reasons_map = checker.analyze_unassigned(result.get('unassigned', []))

    for unassigned in result.get('unassigned', []):
        unassigned['reasons'] = reasons_map.get(unassigned['id'], [])

    analyzer = ResultAnalyzer()
    analysis = analyzer.analyze(vrp_dict, result)

    stats_gen = StatisticsGenerator()
    statistics = stats_gen.generate(result)

    # 7. 결과 통합
    final_result = {
        **result,
        'analysis': analysis,
        'statistics': statistics,
        'metadata': {
            'processing_time_ms': int((time.time() - start_time) * 1000),
            'priority': priority,
            'used_cache': False,
            'used_multi_scenario': use_multi_scenario,
            'used_external_enrichment': enrich_external,
            'used_auto_tune': auto_tune,
            'client': api_key_info['name'],
            'wrapper_version': '2.0'
        }
    }

    # 8. 캐싱
    if use_cache:
        cache_manager.set(vrp_dict, final_result)

    return final_result
```

---

## 📅 구현 일정

### Week 1-2: Phase 1 (전처리)
- [ ] Day 1-2: InputValidator (Pydantic 모델)
- [ ] Day 3-4: InputNormalizer (좌표/시간 정규화)
- [ ] Day 5-7: BusinessRuleEngine (VIP, 긴급, 지역 제약)
- [ ] Day 8-10: 통합 테스트

### Week 3-4: Phase 2 (제어)
- [ ] Day 1-3: VROOMConfigManager (동적 설정)
- [ ] Day 4-6: ConstraintTuner (자동 튜닝)
- [ ] Day 7-10: MultiScenarioEngine (병렬 최적화)
- [ ] Day 11-14: 통합 테스트

### Week 5-6: Phase 3 (후처리)
- [ ] Day 1-3: ResultAnalyzer 확장 (품질 점수, 추천)
- [ ] Day 4-6: StatisticsGenerator (통계 생성)
- [ ] Day 7-10: CostCalculator (비용/탄소)
- [ ] Day 11-14: 통합 테스트

### Week 7-8: Phase 4 (확장)
- [ ] Day 1-4: ExternalAPIIntegrator (날씨, 교통, 지오코딩)
- [ ] Day 5-7: CacheManager (Redis)
- [ ] Day 8-10: RateLimiter & Auth (slowapi)
- [ ] Day 11-14: 통합 테스트 및 문서화

### Week 9-10: 통합 및 최적화
- [ ] Day 1-3: 전체 파이프라인 통합
- [ ] Day 4-6: 성능 최적화
- [ ] Day 7-10: 대규모 테스트 (2000 jobs, 250 vehicles)
- [ ] Day 11-14: API 문서 업데이트, 배포 준비

---

## 🧪 테스트 전략

### 단위 테스트
```python
# tests/test_input_normalizer.py
def test_coordinate_normalization():
    normalizer = InputNormalizer()

    # 딕셔너리 형식 좌표
    result = normalizer._to_lon_lat({'lon': 126.9, 'lat': 37.5})
    assert result == [126.9, 37.5]

    # 이미 표준 형식
    result = normalizer._to_lon_lat([126.9, 37.5])
    assert result == [126.9, 37.5]

def test_time_normalization():
    normalizer = InputNormalizer()

    # "HH:MM" 형식
    result = normalizer._to_seconds("09:30")
    assert result == 34200  # 9.5 hours * 3600

    # 이미 초 단위
    result = normalizer._to_seconds(36000)
    assert result == 36000
```

### 통합 테스트
```python
# tests/test_integration.py
@pytest.mark.asyncio
async def test_full_pipeline():
    """전체 파이프라인 테스트"""
    vrp_input = {
        'vehicles': [{'id': 1, 'start': [126.9, 37.5]}],
        'jobs': [
            {'id': 1, 'location': [127.0, 37.6], 'service': 300},
            {'id': 2, 'location': [126.8, 37.4], 'service': 600}
        ]
    }

    result = await optimize_v2(
        vrp_input,
        priority='balanced',
        use_cache=False,
        use_multi_scenario=True
    )

    assert result['code'] == 0
    assert 'analysis' in result
    assert 'statistics' in result
    assert 'metadata' in result
```

### 성능 테스트
```python
# tests/test_performance.py
def test_large_scale_performance():
    """대규모 테스트 (2000 jobs, 250 vehicles)"""
    vrp_input = generate_large_input(num_jobs=2000, num_vehicles=250)

    start = time.time()
    result = optimize_v2(vrp_input, priority='speed')
    duration = time.time() - start

    assert duration < 600  # 10분 이내
    assert len(result.get('unassigned', [])) < 100  # 95% 이상 배정
```

---

## 📖 API 문서 업데이트

`API-DOCUMENTATION.md`에 v2 엔드포인트 추가:

```markdown
## POST /optimize/v2

완전한 통제 기능을 갖춘 v2.0 최적화 엔드포인트

### 요청 파라미터

| 파라미터 | 타입 | 기본값 | 설명 |
|---------|------|--------|------|
| priority | string | balanced | 'speed', 'balanced', 'quality' |
| use_cache | boolean | true | 결과 캐싱 사용 |
| use_multi_scenario | boolean | false | 다중 시나리오 병렬 실행 |
| enrich_external | boolean | false | 외부 API 데이터 추가 |
| auto_tune | boolean | true | 자동 제약조건 튜닝 |

### 응답 예시

```json
{
  "code": 0,
  "summary": {...},
  "routes": [...],
  "unassigned": [
    {
      "id": 101,
      "location": [127.0, 37.5],
      "reasons": [
        {
          "type": "time_window",
          "reason": "Time window [09:00-10:00] too tight",
          "severity": "high"
        }
      ]
    }
  ],
  "analysis": {
    "quality_score": {
      "score": 87.5,
      "assignment_rate": 95.2
    },
    "recommendations": [
      "Consider relaxing time windows for 3 jobs"
    ],
    "cost_breakdown": {
      "total_cost_krw": 450000,
      "carbon_footprint_kg": 125.3
    }
  },
  "statistics": {
    "vehicle_statistics": [...],
    "hourly_distribution": {...}
  },
  "metadata": {
    "processing_time_ms": 3450,
    "wrapper_version": "2.0"
  }
}
```
```

---

## 🔧 dependencies 업데이트

```txt
# requirements.txt에 추가

# 기존
fastapi==0.104.1
uvicorn==0.24.0
requests==2.31.0

# 추가 (Phase 1-4)
pydantic==2.5.0          # 입력 검증
slowapi==0.1.9           # Rate limiting
redis==5.0.1             # 캐싱
httpx==0.25.2            # 비동기 HTTP
PyYAML==6.0.1            # YAML 설정
pytest==7.4.3            # 테스트
pytest-asyncio==0.21.1   # 비동기 테스트
```

---

## 🎯 성공 지표

### 기능적 목표
- ✅ 95% 이상 작업 배정률 달성
- ✅ 미배정 사유 100% 정확도
- ✅ 외부 API 연동 (날씨, 교통, 지오코딩)
- ✅ 다중 시나리오 병렬 실행
- ✅ 자동 제약조건 튜닝

### 성능 목표
- ✅ 50 jobs: < 10초
- ✅ 500 jobs: < 60초
- ✅ 2000 jobs: < 600초 (10분)
- ✅ API 응답 시간 < 5초 (캐시 hit)

### 운영 목표
- ✅ API 가용성 99.9%
- ✅ Rate Limiting 적용
- ✅ API Key 인증
- ✅ 모니터링 & 로깅

---

## 📚 참고 자료

- [VROOM API 문서](http://vroom-project.org/api.html)
- [OSRM HTTP API](http://project-osrm.org/docs/v5.24.0/api/)
- [FastAPI 문서](https://fastapi.tiangolo.com/)
- [Pydantic 문서](https://docs.pydantic.dev/)

---

**준비 완료!** 이제 Wrapper는 단순한 미배정 사유 분석을 넘어 완전한 VRP 최적화 플랫폼이 됩니다! 🚀
