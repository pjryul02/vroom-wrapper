# OSRM vs 실시간 ETA: 작동 메커니즘 완전 분석

**핵심 질문**: OSRM이 하는 일 vs Wrapper가 해야 하는 일

---

## 1. OSRM의 역할과 한계

### 1.1 OSRM이 제공하는 것

```
┌─────────────────────────────────────────────────────────┐
│ OSRM (Open Source Routing Machine)                      │
│                                                          │
│ 입력: 좌표 A, 좌표 B                                     │
│ 출력: 도로망 기반 최단 경로                              │
│                                                          │
│ ✅ 제공하는 것:                                         │
│  • 도로망 벡터 데이터 (정적)                            │
│  • 거리 (distance in meters)                           │
│  • 이론적 주행 시간 (duration in seconds)               │
│  • 경로 geometry (좌표 리스트)                          │
│  • 턴바이턴 내비게이션 (옵션)                           │
│                                                          │
│ ❌ 제공하지 않는 것:                                    │
│  • 실시간 교통 정보                                     │
│  • 시간대별 교통 패턴                                   │
│  • 사고/공사 정보                                       │
│  • 날씨 영향                                            │
│  • 특정 시간대 도착 예정 시간 (타임머신)                 │
└─────────────────────────────────────────────────────────┘
```

### 1.2 OSRM 예시

```bash
# OSRM 호출 (서울 강남 → 판교)
curl "http://localhost:5000/route/v1/driving/127.0276,37.4979;127.1086,37.3913?overview=full"

# 응답
{
  "routes": [{
    "distance": 18543.2,        # 18.5km (도로망 기준)
    "duration": 1326.8,         # 22분 6초 (이론적 시간, 속도 기반)
    "geometry": "...",          # 경로 좌표
    "legs": [...]
  }]
}
```

**문제점**:
- `duration: 1326.8초`는 **이론적 시간** (도로 제한속도 기반)
- 실제로는:
  - 오전 8시 출근 시간: 40분 소요 (교통 체증)
  - 오후 2시 한가한 시간: 18분 소요
  - 비오는 날: 30분 소요

---

## 2. 실시간 ETA를 위한 Wrapper의 역할

### 2.1 타임머신 ETA란?

```
타임머신 ETA = "특정 출발 시각"에 출발했을 때, 각 경유지의 "실제 도착 시간"

예시:
- 출발: 오늘 08:00 (강남)
- 경유지 1: 판교 → 실시간 교통 고려 시 08:42 도착 (OSRM: 08:22)
- 경유지 2: 용인 → 08:42 출발 → 09:15 도착 (OSRM: 09:00)
- ...
```

### 2.2 Wrapper가 해야 할 일

```python
# eta_calculator.py (새 모듈)

from typing import List, Dict, Tuple
from datetime import datetime, timedelta
import httpx
import logging

logger = logging.getLogger(__name__)

class ETACalculator:
    """실시간 ETA 계산기"""

    def __init__(self):
        self.kakao_api_key = os.getenv('KAKAO_API_KEY')
        self.google_api_key = os.getenv('GOOGLE_API_KEY')
        self.tomtom_api_key = os.getenv('TOMTOM_API_KEY')

    async def enrich_routes_with_realtime_eta(
        self,
        routes: List[Dict],
        departure_time: datetime
    ) -> List[Dict]:
        """
        VROOM 결과에 실시간 ETA 추가

        VROOM이 반환한 routes는:
        - OSRM의 정적 거리/시간 기반
        - 각 step의 arrival은 이론적 시간

        이 함수는:
        - 각 step별로 실시간 API 호출
        - 실제 교통 상황 반영한 ETA 계산
        - step.arrival과 step.real_eta를 모두 제공
        """
        logger.info(
            f"Enriching {len(routes)} routes with real-time ETA "
            f"(departure: {departure_time})"
        )

        enriched_routes = []

        for route in routes:
            enriched_route = await self._enrich_single_route(
                route,
                departure_time
            )
            enriched_routes.append(enriched_route)

        return enriched_routes

    async def _enrich_single_route(
        self,
        route: Dict,
        departure_time: datetime
    ) -> Dict:
        """단일 경로 enrichment"""
        steps = route.get('steps', [])

        if not steps:
            return route

        current_time = departure_time
        enriched_steps = []

        for i, step in enumerate(steps):
            enriched_step = step.copy()

            # 출발지/종료지는 건너뜀
            if step['type'] in ['start', 'end']:
                enriched_step['real_eta'] = None
                enriched_steps.append(enriched_step)
                continue

            # 이전 step에서 현재 step까지의 실시간 ETA 계산
            if i > 0:
                prev_step = steps[i - 1]
                origin = self._get_location(prev_step)
                destination = self._get_location(step)

                # 실시간 API 호출
                real_duration = await self._get_realtime_duration(
                    origin,
                    destination,
                    current_time
                )

                # 서비스 시간 추가
                service_time = step.get('service', 0)
                total_duration = real_duration + service_time

                # 실제 도착 시간
                real_arrival = current_time + timedelta(seconds=total_duration)

                enriched_step['real_eta'] = real_arrival.isoformat()
                enriched_step['real_duration_from_prev'] = real_duration
                enriched_step['osrm_duration_from_prev'] = step.get('duration', 0)
                enriched_step['eta_diff_seconds'] = real_duration - step.get('duration', 0)

                # 다음 step의 출발 시간 업데이트
                current_time = real_arrival

            enriched_steps.append(enriched_step)

        route['steps'] = enriched_steps
        route['_real_eta_calculated'] = True

        return route

    def _get_location(self, step: Dict) -> Tuple[float, float]:
        """Step에서 좌표 추출"""
        if 'location' in step:
            return tuple(step['location'])
        # start/end의 경우
        return None

    async def _get_realtime_duration(
        self,
        origin: Tuple[float, float],
        destination: Tuple[float, float],
        departure_time: datetime
    ) -> int:
        """
        실시간/타임머신 기반 주행 시간 계산

        우선순위:
        1. Google Maps Directions API (가장 정확, 유료)
        2. Kakao Mobility API (한국 특화, 유료)
        3. TomTom Traffic API (글로벌, 유료)
        4. OSRM (fallback, 무료이지만 정적)
        """
        try:
            # 1순위: Google Maps
            if self.google_api_key:
                duration = await self._google_directions(
                    origin, destination, departure_time
                )
                if duration:
                    logger.debug(f"Using Google Maps: {duration}s")
                    return duration

        except Exception as e:
            logger.warning(f"Google Maps API error: {e}")

        try:
            # 2순위: Kakao Mobility
            if self.kakao_api_key:
                duration = await self._kakao_directions(
                    origin, destination, departure_time
                )
                if duration:
                    logger.debug(f"Using Kakao: {duration}s")
                    return duration

        except Exception as e:
            logger.warning(f"Kakao API error: {e}")

        # Fallback: OSRM (정적)
        logger.warning("Using OSRM as fallback (no real-time data)")
        return await self._osrm_duration(origin, destination)

    async def _google_directions(
        self,
        origin: Tuple[float, float],
        destination: Tuple[float, float],
        departure_time: datetime
    ) -> int:
        """
        Google Maps Directions API

        특징:
        - 실시간 교통 정보 포함
        - departure_time 지원 (타임머신)
        - arrival_time도 지원 (역방향 계산)
        - 매우 정확
        """
        async with httpx.AsyncClient() as client:
            params = {
                'origin': f"{origin[1]},{origin[0]}",  # lat,lon
                'destination': f"{destination[1]},{destination[0]}",
                'departure_time': int(departure_time.timestamp()),
                'traffic_model': 'best_guess',  # 'best_guess' | 'pessimistic' | 'optimistic'
                'key': self.google_api_key
            }

            response = await client.get(
                "https://maps.googleapis.com/maps/api/directions/json",
                params=params,
                timeout=5.0
            )

            data = response.json()

            if data['status'] == 'OK':
                # duration_in_traffic: 실시간 교통 반영
                leg = data['routes'][0]['legs'][0]
                return leg['duration_in_traffic']['value']  # seconds

        return None

    async def _kakao_directions(
        self,
        origin: Tuple[float, float],
        destination: Tuple[float, float],
        departure_time: datetime
    ) -> int:
        """
        Kakao Mobility API

        특징:
        - 한국 도로 최적화
        - 실시간 교통 정보
        - 무료 쿼터 제한
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://apis-navi.kakaomobility.com/v1/directions",
                headers={'Authorization': f'KakaoAK {self.kakao_api_key}'},
                params={
                    'origin': f"{origin[0]},{origin[1]}",
                    'destination': f"{destination[0]},{destination[1]}",
                    'waypoints': '',
                    'priority': 'RECOMMEND',  # 추천 경로
                    'car_fuel': 'GASOLINE',
                    'car_hipass': 'false',
                    'alternatives': 'false',
                    'road_details': 'false'
                },
                timeout=5.0
            )

            data = response.json()

            if data.get('routes'):
                # duration: 실시간 교통 반영된 예상 시간
                return data['routes'][0]['summary']['duration']  # seconds

        return None

    async def _osrm_duration(
        self,
        origin: Tuple[float, float],
        destination: Tuple[float, float]
    ) -> int:
        """OSRM fallback (정적 데이터)"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"http://localhost:5000/route/v1/driving/"
                f"{origin[0]},{origin[1]};{destination[0]},{destination[1]}",
                params={'overview': 'false'},
                timeout=5.0
            )

            data = response.json()

            if data['code'] == 'Ok':
                return int(data['routes'][0]['duration'])

        return 0
```

### 2.3 사용 예시

```python
# VROOM 최적화 후
result = call_vroom(vrp_input)

# 실시간 ETA로 enrichment
eta_calculator = ETACalculator()
result['routes'] = await eta_calculator.enrich_routes_with_realtime_eta(
    result['routes'],
    departure_time=datetime(2024, 1, 23, 8, 0)  # 오늘 오전 8시 출발
)

# 결과
{
  "routes": [{
    "vehicle": 1,
    "steps": [
      {
        "type": "start",
        "location": [126.9780, 37.5665],
        "arrival": 28800,  # 08:00 (OSRM 이론값)
        "real_eta": null
      },
      {
        "type": "job",
        "id": 101,
        "location": [127.0276, 37.4979],
        "arrival": 30126,  # 08:22 (OSRM 이론값: +22분)
        "real_eta": "2024-01-23T08:42:00",  # 실제 ETA: +42분 (교통 체증)
        "real_duration_from_prev": 2520,  # 42분
        "osrm_duration_from_prev": 1326,  # 22분
        "eta_diff_seconds": 1194,  # +20분 차이
        "service": 300
      },
      {
        "type": "job",
        "id": 102,
        "location": [127.1086, 37.3913],
        "arrival": 32000,  # 08:53 (OSRM 이론값)
        "real_eta": "2024-01-23T09:15:00",  # 실제 ETA: 09:15
        "eta_diff_seconds": 1320  # +22분 차이
      }
    ]
  }]
}
```

---

## 3. OSRM vs 실시간 API 비교표

| 측면 | OSRM | Google Maps | Kakao Mobility | TomTom Traffic |
|-----|------|-------------|----------------|----------------|
| **데이터** | 정적 도로망 | 실시간 교통 | 실시간 교통 (한국) | 실시간 교통 |
| **타임머신** | ❌ | ✅ (departure_time) | ⚠️ (제한적) | ✅ |
| **비용** | 무료 | 유료 | 무료→유료 | 유료 |
| **정확도** | 70% | 95% | 90% (한국) | 90% |
| **속도** | 매우 빠름 | 보통 | 빠름 | 보통 |
| **용도** | 경로 최적화 | 실제 ETA | 실제 ETA (한국) | 실제 ETA |

---

## 4. Wrapper 통합 전략

### 4.1 2단계 접근

```
Step 1: VROOM + OSRM (빠른 최적화)
  • 정적 도로망 기반 경로 생성
  • 이론적 도착 시간 계산
  • 최적화에 집중

Step 2: 실시간 ETA Enrichment (정확한 예측)
  • Google/Kakao API 호출
  • 실시간 교통 정보 반영
  • 실제 도착 시간 예측
```

### 4.2 최종 엔드포인트

```python
@app.post("/optimize/v2")
async def optimize_v2_with_realtime_eta(
    vrp_input: Dict,
    departure_time: Optional[datetime] = None,
    use_realtime_eta: bool = False,  # 실시간 ETA 사용 여부
    ...
):
    """v2.0 최적화 + 실시간 ETA"""

    # 1-3단계: 기존 로직 (전처리, 최적화, 후처리)
    result = await controller.optimize(vrp_input, strategy, priority)

    # 4단계: 실시간 ETA enrichment (옵션)
    if use_realtime_eta:
        if not departure_time:
            departure_time = datetime.now()

        eta_calculator = ETACalculator()
        result['routes'] = await eta_calculator.enrich_routes_with_realtime_eta(
            result['routes'],
            departure_time
        )

        logger.info("✓ Real-time ETA calculated")

    return result
```

### 4.3 비용 최적화 전략

실시간 API는 비용이 발생하므로:

```python
class ETACalculator:
    def __init__(self):
        self.use_cache = True  # ETA 캐싱
        self.cache_ttl = 300  # 5분

    async def _get_realtime_duration(self, origin, dest, dep_time):
        # 캐시 확인
        cache_key = f"{origin}:{dest}:{dep_time.hour}"
        if self.use_cache:
            cached = cache_manager.get(cache_key)
            if cached:
                return cached

        # API 호출
        duration = await self._google_directions(...)

        # 캐싱 (5분간 유효)
        cache_manager.set(cache_key, duration, ttl=self.cache_ttl)

        return duration
```

---

## 5. 실전 사용 시나리오

### 시나리오 1: 빠른 최적화 (실시간 ETA 불필요)

```python
# OSRM만 사용 (무료, 빠름)
result = await optimize_v2(
    vrp_input,
    use_realtime_eta=False  # OSRM 정적 데이터만
)

# 용도: 초기 경로 계획, 시뮬레이션
```

### 시나리오 2: 정확한 배차 계획 (실시간 ETA 필수)

```python
# Google Maps/Kakao API 사용 (유료, 정확)
result = await optimize_v2(
    vrp_input,
    departure_time=datetime(2024, 1, 23, 8, 0),
    use_realtime_eta=True  # 실시간 교통 반영
)

# 용도: 실제 배차 실행, 고객 알림
```

### 시나리오 3: 하이브리드 (중요 경로만 실시간)

```python
# 우선순위 높은 작업만 실시간 ETA 계산
result = await optimize_v2(vrp_input, use_realtime_eta=False)

# 후처리: VIP 고객 경로만 실시간 ETA 추가
vip_routes = [r for r in result['routes'] if has_vip_jobs(r)]
for route in vip_routes:
    route = await eta_calculator.enrich_single_route(route, departure_time)
```

---

## 6. 요약

| 질문 | 답변 |
|-----|------|
| OSRM이 실시간 교통을 고려하나? | ❌ 아니요. 정적 도로망 기반 이론값만 |
| VROOM의 arrival 시간이 정확한가? | ⚠️ OSRM 기반이므로 이론값 (실제와 차이) |
| 실시간 ETA는 어떻게? | ✅ Wrapper가 Google/Kakao API 호출 |
| 타임머신 ETA (특정 시각 출발)는? | ✅ Google departure_time 파라미터 사용 |
| 비용은? | OSRM 무료, 실시간 API 유료 |
| 언제 실시간 API를 써야? | 실제 배차 실행, 고객 알림 시 |

**핵심**: OSRM = 최적화용, Google/Kakao = 실행용(정확한 ETA)
