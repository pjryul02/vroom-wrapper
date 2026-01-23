# VROOM Wrapper 아키텍처 및 확장 가이드

## 개요

Wrapper는 단순한 API 게이트웨이가 아닌, **배차 최적화의 중앙 제어 레이어**입니다.

### 핵심 역할

1. **전처리 (Pre-processing)**: 입력 검증, 변환, 비즈니스 로직 적용
2. **제어 (Control)**: VROOM 엔진 설정, 제약 조건 조절
3. **후처리 (Post-processing)**: 결과 분석, 품질 평가, 통계
4. **확장 (Extension)**: 커스텀 로직, 외부 서비스 통합

---

## 📐 현재 아키텍처 (v1.0)

### 기본 구조

```python
@app.post("/optimize")
async def optimize_with_reasons(vrp_input: Dict[str, Any]):
    # 1. 입력 저장
    checker = ConstraintChecker(vrp_input)

    # 2. VROOM 호출
    response = requests.post(VROOM_URL, json=vrp_input)
    result = response.json()

    # 3. 미배정 이유 분석
    if result.get('unassigned'):
        reasons_map = checker.analyze_unassigned(result['unassigned'])
        for unassigned in result['unassigned']:
            unassigned['reasons'] = reasons_map[unassigned['id']]

    # 4. 반환
    return result
```

### 한계점

- ❌ 입력 검증 없음
- ❌ 비즈니스 로직 적용 불가
- ❌ 제약 조건 동적 조절 불가
- ❌ 경로 품질 평가 없음
- ❌ 통계/모니터링 부족

---

## 🏗️ 확장 아키텍처 (v2.0)

### 레이어 구조

```
┌─────────────────────────────────────────────────────┐
│                  API Layer                           │
│  • 인증/권한                                          │
│  • Rate Limiting                                     │
│  • Request Validation                                │
└─────────────────┬───────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────────────────┐
│              Pre-processor Layer                     │
│  • Input Normalization                               │
│  • Business Rules                                    │
│  • Constraint Transformation                         │
│  • Priority Calculation                              │
└─────────────────┬───────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────────────────┐
│              VROOM Controller                        │
│  • Dynamic Configuration                             │
│  • Constraint Tuning                                 │
│  • Engine Selection (VROOM/OR-Tools/etc)            │
└─────────────────┬───────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────────────────┐
│                VROOM Engine                          │
└─────────────────┬───────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────────────────┐
│             Post-processor Layer                     │
│  • Result Analysis                                   │
│  • Unassigned Reason Detection                       │
│  • Route Quality Scoring                             │
│  • Cost Breakdown                                    │
│  • Statistics Generation                             │
└─────────────────┬───────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────────────────┐
│              Response Layer                          │
│  • Format Transformation                             │
│  • Data Enrichment                                   │
│  • Logging/Monitoring                                │
└─────────────────────────────────────────────────────┘
```

---

## 🔧 확장 영역 상세

### 1. 전처리 (Pre-processing)

#### 1.1 입력 정규화 (Input Normalization)

```python
class InputNormalizer:
    """입력 데이터 정규화 및 검증"""

    def normalize(self, raw_input: Dict) -> Dict:
        """
        - 좌표 형식 통일 ([lon, lat])
        - 시간 형식 통일 (초 단위)
        - 용량 차원 정렬
        - 누락된 필수 필드 추가
        """
        normalized = raw_input.copy()

        # 예: 주소 → 좌표 변환
        for job in normalized.get('jobs', []):
            if 'address' in job and 'location' not in job:
                job['location'] = self.geocode(job['address'])

        # 예: 시간 형식 변환 (HH:MM → 초)
        for vehicle in normalized.get('vehicles', []):
            if 'time_window_str' in vehicle:
                vehicle['time_window'] = self.parse_time_window(
                    vehicle['time_window_str']
                )

        return normalized

    def validate(self, input_data: Dict) -> List[str]:
        """입력 검증 및 에러 목록 반환"""
        errors = []

        if not input_data.get('vehicles'):
            errors.append("No vehicles provided")

        if not input_data.get('jobs') and not input_data.get('shipments'):
            errors.append("No jobs or shipments provided")

        # 좌표 범위 검증
        for job in input_data.get('jobs', []):
            loc = job.get('location', [])
            if len(loc) != 2:
                errors.append(f"Job {job['id']}: Invalid location format")
            elif not (-180 <= loc[0] <= 180 and -90 <= loc[1] <= 90):
                errors.append(f"Job {job['id']}: Invalid coordinates")

        return errors
```

#### 1.2 비즈니스 로직 적용

```python
class BusinessRuleEngine:
    """비즈니스 규칙 엔진"""

    def apply_rules(self, input_data: Dict) -> Dict:
        """비즈니스 규칙 적용"""

        # 규칙 1: VIP 고객 우선순위 자동 상향
        for job in input_data.get('jobs', []):
            if job.get('customer_type') == 'VIP':
                job['priority'] = 100
            elif job.get('customer_type') == 'standard':
                job['priority'] = job.get('priority', 50)

        # 규칙 2: 긴급 주문 시간 윈도우 확장
        for job in input_data.get('jobs', []):
            if job.get('is_urgent'):
                # 시간 윈도우 2배 확장
                if job.get('time_windows'):
                    original_tw = job['time_windows'][0]
                    duration = original_tw[1] - original_tw[0]
                    job['time_windows'] = [[
                        original_tw[0] - duration,
                        original_tw[1] + duration
                    ]]

        # 규칙 3: 지역별 차량 할당 제약
        for vehicle in input_data.get('vehicles', []):
            zone = vehicle.get('assigned_zone')
            if zone:
                # 해당 지역의 작업만 할당되도록 필터링
                vehicle['allowed_job_zones'] = [zone]

        return input_data

    def calculate_dynamic_priority(self, job: Dict) -> int:
        """동적 우선순위 계산"""
        priority = 50  # 기본값

        # 요인 1: 고객 등급
        customer_tier = {
            'VIP': 30,
            'premium': 20,
            'standard': 0
        }
        priority += customer_tier.get(job.get('customer_type'), 0)

        # 요인 2: 배송 시간 긴급도
        time_window = job.get('time_windows', [[]])[0]
        if time_window:
            time_left = time_window[1] - time.time()
            if time_left < 3600:  # 1시간 이내
                priority += 20
            elif time_left < 7200:  # 2시간 이내
                priority += 10

        # 요인 3: 주문 금액
        order_value = job.get('order_value', 0)
        if order_value > 100000:  # 10만원 이상
            priority += 15

        return min(priority, 100)  # 최대 100
```

#### 1.3 제약 조건 변환

```python
class ConstraintTransformer:
    """제약 조건 변환 및 최적화"""

    def transform_constraints(self, input_data: Dict) -> Dict:
        """비즈니스 제약 → VROOM 제약 변환"""

        # 예: 차량 그룹 제약
        # "냉장 차량만 냉장 제품 배송"
        for vehicle in input_data.get('vehicles', []):
            if vehicle.get('type') == 'refrigerated':
                vehicle.setdefault('skills', []).append(99)  # 냉장 스킬

        for job in input_data.get('jobs', []):
            if job.get('product_type') == 'frozen':
                job.setdefault('skills', []).append(99)

        # 예: 시간대별 교통량 반영
        current_hour = datetime.now().hour
        if 7 <= current_hour <= 9 or 17 <= current_hour <= 19:
            # 출퇴근 시간: 모든 차량 속도 0.7배
            for vehicle in input_data.get('vehicles', []):
                vehicle['speed_factor'] = 0.7

        return input_data

    def optimize_time_windows(self, input_data: Dict) -> Dict:
        """시간 윈도우 최적화"""

        for job in input_data.get('jobs', []):
            time_windows = job.get('time_windows', [])

            # 좁은 시간 윈도우 완화 (배정 가능성 증가)
            for tw in time_windows:
                duration = tw[1] - tw[0]
                if duration < 1800:  # 30분 미만
                    # 앞뒤로 15분씩 확장
                    tw[0] -= 900
                    tw[1] += 900

        return input_data
```

### 2. VROOM 제어 (Control)

#### 2.1 동적 설정

```python
class VROOMController:
    """VROOM 엔진 제어"""

    def __init__(self):
        self.vroom_url = "http://localhost:3000"
        self.default_config = {
            "exploration_level": 5,
            "threads": 4
        }

    def optimize_with_config(self,
                            vrp_input: Dict,
                            config: Dict = None) -> Dict:
        """설정을 적용하여 최적화"""

        config = config or self.default_config

        # 작업 수에 따라 exploration_level 조정
        job_count = len(vrp_input.get('jobs', []))
        if job_count > 500:
            config['exploration_level'] = 3  # 빠른 처리
        elif job_count < 50:
            config['exploration_level'] = 7  # 더 정확한 결과

        # VROOM 호출 (설정 포함)
        response = requests.post(
            self.vroom_url,
            json=vrp_input,
            params=config,
            timeout=300
        )

        return response.json()

    def multi_scenario_optimization(self, vrp_input: Dict) -> Dict:
        """여러 시나리오로 최적화 후 최선 선택"""

        scenarios = [
            {"exploration_level": 3, "name": "fast"},
            {"exploration_level": 5, "name": "balanced"},
            {"exploration_level": 7, "name": "accurate"}
        ]

        results = []
        for scenario in scenarios:
            result = self.optimize_with_config(vrp_input, scenario)
            result['_scenario'] = scenario['name']
            results.append(result)

        # 미배정 최소화 + 총 거리 최소화
        best = min(results, key=lambda r: (
            len(r['unassigned']),
            r['summary']['distance']
        ))

        return best
```

#### 2.2 제약 조건 튜닝

```python
class ConstraintTuner:
    """제약 조건 자동 조정"""

    def auto_tune(self, vrp_input: Dict) -> Dict:
        """미배정 최소화를 위한 자동 튜닝"""

        # 1차 시도: 원본 입력
        result = self.optimize(vrp_input)

        if len(result['unassigned']) == 0:
            return result

        # 2차 시도: 시간 윈도우 완화
        relaxed = self.relax_time_windows(vrp_input, factor=1.5)
        result2 = self.optimize(relaxed)

        if len(result2['unassigned']) < len(result['unassigned']):
            result2['_tuning_applied'] = 'time_window_relaxed'
            return result2

        # 3차 시도: 우선순위 재조정
        rebalanced = self.rebalance_priorities(vrp_input)
        result3 = self.optimize(rebalanced)

        if len(result3['unassigned']) < len(result['unassigned']):
            result3['_tuning_applied'] = 'priority_rebalanced'
            return result3

        # 최선의 결과 반환
        return min([result, result2, result3],
                   key=lambda r: len(r['unassigned']))

    def relax_time_windows(self, vrp_input: Dict, factor: float) -> Dict:
        """시간 윈도우 완화"""
        relaxed = vrp_input.copy()

        for job in relaxed.get('jobs', []):
            if job.get('time_windows'):
                for tw in job['time_windows']:
                    duration = tw[1] - tw[0]
                    expansion = (duration * (factor - 1)) / 2
                    tw[0] -= expansion
                    tw[1] += expansion

        return relaxed
```

### 3. 후처리 (Post-processing)

#### 3.1 결과 분석

```python
class ResultAnalyzer:
    """결과 분석 및 품질 평가"""

    def analyze(self, result: Dict, original_input: Dict) -> Dict:
        """종합 분석"""

        analysis = {
            "quality_score": self.calculate_quality_score(result),
            "efficiency_metrics": self.calculate_efficiency(result),
            "constraint_violations": self.check_violations(result),
            "cost_breakdown": self.breakdown_costs(result),
            "recommendations": self.generate_recommendations(result)
        }

        result['_analysis'] = analysis
        return result

    def calculate_quality_score(self, result: Dict) -> float:
        """경로 품질 점수 (0-100)"""
        score = 100.0

        # 미배정 패널티
        total_jobs = len(result.get('unassigned', [])) + sum(
            len([s for s in r['steps'] if s['type'] == 'job'])
            for r in result.get('routes', [])
        )
        unassigned_ratio = len(result['unassigned']) / total_jobs
        score -= unassigned_ratio * 50  # 최대 50점 감점

        # 차량 활용도
        used_vehicles = len(result.get('routes', []))
        if used_vehicles == 0:
            return 0.0

        # 균등 배분 점수
        job_counts = [
            len([s for s in r['steps'] if s['type'] == 'job'])
            for r in result['routes']
        ]
        avg_jobs = sum(job_counts) / len(job_counts)
        variance = sum((x - avg_jobs) ** 2 for x in job_counts) / len(job_counts)
        balance_score = 100 / (1 + variance)  # 분산이 낮을수록 높은 점수
        score = (score + balance_score) / 2

        return round(score, 2)

    def calculate_efficiency(self, result: Dict) -> Dict:
        """효율성 지표"""
        routes = result.get('routes', [])

        total_distance = sum(r['distance'] for r in routes)
        total_duration = sum(r['duration'] for r in routes)
        total_jobs = sum(
            len([s for s in r['steps'] if s['type'] == 'job'])
            for r in routes
        )

        return {
            "avg_distance_per_job": total_distance / total_jobs if total_jobs > 0 else 0,
            "avg_duration_per_job": total_duration / total_jobs if total_jobs > 0 else 0,
            "vehicle_utilization": len(routes) / len(result.get('routes', [1])),
            "jobs_per_vehicle": total_jobs / len(routes) if routes else 0
        }

    def generate_recommendations(self, result: Dict) -> List[str]:
        """개선 권장사항"""
        recommendations = []

        # 미배정 많음
        if len(result['unassigned']) > 10:
            recommendations.append(
                f"{len(result['unassigned'])}개 작업 미배정됨. "
                "차량 추가 또는 제약 완화 권장"
            )

        # 특정 차량에 작업 집중
        job_counts = [
            len([s for s in r['steps'] if s['type'] == 'job'])
            for r in result.get('routes', [])
        ]
        max_jobs = max(job_counts) if job_counts else 0
        avg_jobs = sum(job_counts) / len(job_counts) if job_counts else 0

        if max_jobs > avg_jobs * 2:
            recommendations.append(
                f"작업 분배 불균형 (최대: {max_jobs}개, 평균: {avg_jobs:.1f}개). "
                "차량 max_tasks 조정 권장"
            )

        return recommendations
```

#### 3.2 통계 생성

```python
class StatisticsGenerator:
    """통계 생성"""

    def generate(self, result: Dict, original_input: Dict) -> Dict:
        """종합 통계"""

        stats = {
            "summary": self.generate_summary(result),
            "by_vehicle": self.generate_vehicle_stats(result),
            "by_skill": self.generate_skill_stats(result, original_input),
            "by_time": self.generate_time_stats(result),
            "violations": self.generate_violation_stats(result)
        }

        return stats

    def generate_vehicle_stats(self, result: Dict) -> List[Dict]:
        """차량별 통계"""
        stats = []

        for route in result.get('routes', []):
            job_steps = [s for s in route['steps'] if s['type'] == 'job']

            stats.append({
                "vehicle_id": route['vehicle'],
                "total_jobs": len(job_steps),
                "total_distance": route['distance'],
                "total_duration": route['duration'],
                "avg_service_time": (
                    sum(s.get('service', 0) for s in job_steps) / len(job_steps)
                    if job_steps else 0
                ),
                "violations": route.get('violations', [])
            })

        return stats
```

### 4. 확장 기능 (Extensions)

#### 4.1 외부 서비스 통합

```python
class ExternalServiceIntegrator:
    """외부 서비스 통합"""

    def __init__(self):
        self.weather_api = WeatherAPI()
        self.traffic_api = TrafficAPI()
        self.geocoding_api = GeocodingAPI()

    def enrich_with_weather(self, vrp_input: Dict) -> Dict:
        """날씨 정보 반영"""

        for job in vrp_input.get('jobs', []):
            location = job['location']
            weather = self.weather_api.get_weather(location)

            # 악천후 시 서비스 시간 증가
            if weather['condition'] in ['rain', 'snow']:
                job['service'] = job.get('service', 0) * 1.5

        return vrp_input

    def enrich_with_traffic(self, vrp_input: Dict) -> Dict:
        """실시간 교통 정보 반영"""

        for vehicle in vrp_input.get('vehicles', []):
            start_location = vehicle['start']
            traffic_factor = self.traffic_api.get_traffic_factor(start_location)

            # 교통 상황에 따라 속도 조정
            vehicle['speed_factor'] = 1.0 / traffic_factor

        return vrp_input
```

---

## 🚀 구현 로드맵

### Phase 1: 기본 확장 (1-2주)

- [ ] InputNormalizer 구현
- [ ] BusinessRuleEngine 기본 기능
- [ ] ResultAnalyzer 구현
- [ ] 기본 통계 생성

### Phase 2: 고급 제어 (2-3주)

- [ ] VROOMController 동적 설정
- [ ] ConstraintTuner 자동 조정
- [ ] 다중 시나리오 최적화

### Phase 3: 외부 통합 (2-3주)

- [ ] 날씨 API 통합
- [ ] 실시간 교통 정보
- [ ] Geocoding 서비스

### Phase 4: 프로덕션 준비 (1-2주)

- [ ] 로깅 시스템
- [ ] 모니터링 대시보드
- [ ] 성능 최적화

---

## 📝 사용 예시

### 전체 파이프라인

```python
# vroom_wrapper_v2.py

@app.post("/optimize")
async def optimize_advanced(vrp_input: Dict[str, Any]):
    """고급 최적화 파이프라인"""

    # 1. 전처리
    normalizer = InputNormalizer()
    validated = normalizer.normalize(vrp_input)

    errors = normalizer.validate(validated)
    if errors:
        raise HTTPException(status_code=400, detail=errors)

    # 2. 비즈니스 로직
    rules = BusinessRuleEngine()
    with_rules = rules.apply_rules(validated)

    # 3. 제약 변환
    transformer = ConstraintTransformer()
    transformed = transformer.transform_constraints(with_rules)

    # 4. 최적화 실행
    controller = VROOMController()
    result = controller.optimize_with_config(transformed)

    # 5. 후처리
    analyzer = ResultAnalyzer()
    analyzed = analyzer.analyze(result, vrp_input)

    # 6. 통계 생성
    stats_gen = StatisticsGenerator()
    analyzed['_statistics'] = stats_gen.generate(result, vrp_input)

    # 7. 미배정 이유 (기존 기능)
    checker = ConstraintChecker(vrp_input)
    if result.get('unassigned'):
        reasons_map = checker.analyze_unassigned(result['unassigned'])
        for unassigned in result['unassigned']:
            unassigned['reasons'] = reasons_map[unassigned['id']]

    return analyzed
```

### 응답 예시

```json
{
  "code": 0,
  "summary": {...},
  "routes": [...],
  "unassigned": [
    {
      "id": 102,
      "reasons": [{"type": "skills", ...}]
    }
  ],
  "_analysis": {
    "quality_score": 85.3,
    "efficiency_metrics": {
      "avg_distance_per_job": 2500,
      "vehicle_utilization": 0.8
    },
    "recommendations": [
      "3개 작업 미배정됨. 차량 추가 권장"
    ]
  },
  "_statistics": {
    "by_vehicle": [...],
    "by_skill": [...],
    "violations": [...]
  },
  "_tuning_applied": "time_window_relaxed"
}
```

---

## 🎯 결론

Wrapper는 **단순한 프록시가 아닌 지능형 제어 레이어**로 발전해야 합니다.

### 핵심 가치

1. **유연성**: 비즈니스 로직을 코드 수정 없이 조정
2. **확장성**: 외부 서비스 통합 용이
3. **분석력**: 결과 품질 평가 및 개선 권장
4. **효율성**: 자동 튜닝으로 최적 결과 도출

### 다음 단계

1. 필요한 기능 선택 (Phase 1부터)
2. 점진적 구현
3. 테스트 및 검증
4. 프로덕션 배포

---

**Wrapper를 진화시켜 강력한 배차 플랫폼을 만드세요!** 🚀
