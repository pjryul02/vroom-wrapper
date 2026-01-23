# VROOM Wrapper v2.0 빠른 시작 가이드

## 📋 현재 상태

✅ **완료된 작업**:
- VROOM + OSRM Docker 환경 구축 완료
- Wrapper v1.0 구현 완료 (미배정 사유 분석)
- 전체 아키텍처 설계 완료
- 10주 구현 계획 수립 완료
- 완전한 API 문서 작성 완료
- Git 저장소 구축 완료 (6 commits)

🎯 **다음 단계**: Wrapper v2.0 구현 시작

---

## 🚀 현재 사용 가능한 기능 (v1.0)

### 1. 서비스 시작

```bash
cd /home/shawn/vroom-wrapper-project

# Docker 서비스 시작
docker-compose up -d

# Wrapper 시작
python3 vroom_wrapper.py &
```

### 2. API 호출 (v1.0)

```bash
# 건강 체크
curl http://localhost:8000/health

# 최적화 (미배정 사유 포함)
curl -X POST http://localhost:8000/optimize \
  -H "Content-Type: application/json" \
  -d '{
    "vehicles": [
      {"id": 1, "start": [126.9780, 37.5665], "capacity": [100]}
    ],
    "jobs": [
      {
        "id": 101,
        "location": [127.0276, 37.4979],
        "delivery": [50],
        "skills": [1, 2],
        "time_windows": [[32400, 36000]]
      }
    ]
  }'
```

### 3. 응답 예시 (v1.0)

```json
{
  "code": 0,
  "summary": {
    "cost": 12345,
    "unassigned": 1
  },
  "routes": [...],
  "unassigned": [
    {
      "id": 101,
      "location": [127.0276, 37.4979],
      "reasons": [
        {
          "type": "skills",
          "reason": "Job requires skills [1, 2] but no vehicle has all required skills",
          "severity": "high",
          "details": {...}
        }
      ]
    }
  ]
}
```

---

## 🏗️ v2.0 구현 시작하기

### Phase 1부터 순차적으로 구현

#### Week 1-2: 입력 전처리 강화

**목표**: 다양한 입력 형식 지원 + 비즈니스 로직 적용

```bash
# 1. 현재 vroom_wrapper.py 백업
cp vroom_wrapper.py vroom_wrapper_v1.0.py

# 2. 새 브랜치 생성
git checkout -b feature/phase1-preprocessing

# 3. Phase 1 구현 시작
# WRAPPER-IMPLEMENTATION-PLAN.md의 "Phase 1" 섹션 참고
```

**구현할 컴포넌트**:
1. `InputValidator` (Pydantic 모델) - 입력 검증
2. `InputNormalizer` - 좌표/시간 정규화
3. `BusinessRuleEngine` - VIP/긴급/지역 제약

**테스트**:
```bash
# 단위 테스트 작성
mkdir -p tests
touch tests/test_input_normalizer.py

# 테스트 실행
pytest tests/
```

---

## 📚 주요 문서 가이드

### 읽어야 할 순서

1. **[README.md](README.md)** (5분)
   - 프로젝트 개요, 빠른 시작

2. **[API-DOCUMENTATION.md](API-DOCUMENTATION.md)** (20분)
   - 완전한 API 레퍼런스
   - 5가지 실용 예제
   - Python/JavaScript 클라이언트 라이브러리

3. **[WRAPPER-ARCHITECTURE.md](WRAPPER-ARCHITECTURE.md)** (30분)
   - v1.0 → v2.0 진화 방향
   - 4계층 아키텍처 설계
   - 각 컴포넌트 역할 및 코드 예시

4. **[WRAPPER-IMPLEMENTATION-PLAN.md](WRAPPER-IMPLEMENTATION-PLAN.md)** (1시간)
   - 10주 구현 계획
   - 각 Phase별 상세 코드
   - 테스트 전략 및 성공 지표

5. **[EXTERNAL-ACCESS.md](EXTERNAL-ACCESS.md)** (15분)
   - 외부에서 API 접근 설정
   - Windows 방화벽, 포트포워딩
   - 보안 강화 방법

6. **[docs/VROOM-API-CONTROL-GUIDE.md](docs/VROOM-API-CONTROL-GUIDE.md)** (30분)
   - VROOM 제어 4가지 레벨
   - 설정 파일, 미들웨어, 코어 수정, 래퍼

---

## 💡 구현 우선순위

### 즉시 구현 가능 (1-2주)

이미 코드가 완성되어 있어 복사 붙여넣기로 바로 사용 가능:

1. ✅ **InputValidator** (Pydantic)
   - `WRAPPER-IMPLEMENTATION-PLAN.md` → "1.1 InputValidator" 섹션 코드 복사
   - 즉시 강력한 입력 검증 가능

2. ✅ **InputNormalizer**
   - "1.2 InputNormalizer" 섹션 코드 복사
   - 좌표 형식 (딕셔너리, 리스트, 문자열) 모두 지원
   - 시간 형식 ("09:30", timestamp, ISO 8601) 모두 지원

3. ✅ **BusinessRuleEngine**
   - "1.3 BusinessRuleEngine" 섹션 코드 복사
   - VIP 우선순위, 긴급 주문, 지역 제약 자동 적용

### 중급 난이도 (2-4주)

외부 의존성이 필요하지만 구현 로직은 준비됨:

4. ⚠️ **VROOMConfigManager** (Docker 재시작 필요)
5. ⚠️ **ConstraintTuner** (반복 실행 필요)
6. ⚠️ **MultiScenarioEngine** (병렬 처리)

### 고급 기능 (4-8주)

외부 API 연동 필요:

7. 🔴 **ExternalAPIIntegrator** (Kakao/날씨 API 키 필요)
8. 🔴 **CacheManager** (Redis 설치 필요)
9. 🔴 **RateLimiter & Auth** (slowapi 설정)

---

## 🧪 단계별 테스트 방법

### 1. Phase 1 테스트 (전처리)

```python
# tests/test_phase1.py

def test_input_validator():
    """Pydantic 검증 테스트"""
    from vroom_wrapper import VRPInputModel

    # 잘못된 입력 (좌표 범위 초과)
    with pytest.raises(ValueError):
        VRPInputModel(
            vehicles=[{'id': 1, 'start': [200, 100]}],  # 잘못된 좌표
            jobs=[{'id': 1, 'location': [127, 37]}]
        )

def test_input_normalizer():
    """정규화 테스트"""
    from vroom_wrapper import InputNormalizer

    normalizer = InputNormalizer()

    # 딕셔너리 좌표 -> 리스트 변환
    vrp_input = {
        'vehicles': [{'id': 1, 'start': {'lon': 126.9, 'lat': 37.5}}],
        'jobs': [{'id': 1, 'location': [127.0, 37.6]}]
    }

    result = normalizer.normalize(vrp_input)

    assert result['vehicles'][0]['start'] == [126.9, 37.5]

def test_business_rules():
    """비즈니스 규칙 테스트"""
    from vroom_wrapper import BusinessRuleEngine

    engine = BusinessRuleEngine()

    vrp_input = {
        'vehicles': [{'id': 1, 'start': [126.9, 37.5]}],
        'jobs': [
            {'id': 1, 'location': [127.0, 37.6], 'customer_type': 'VIP'}
        ]
    }

    result = engine.apply_rules(vrp_input, {'vip_priority_boost': True})

    # VIP 우선순위가 증가했는지 확인
    assert result['jobs'][0]['priority'] == 100
```

### 2. Phase 2 테스트 (제어)

```python
# tests/test_phase2.py

def test_config_manager():
    """설정 관리 테스트"""
    from vroom_wrapper import VROOMConfigManager

    manager = VROOMConfigManager()

    # 소규모 시나리오 (50 jobs, 10 vehicles)
    config = manager.optimize_for_scenario(50, 10, priority='quality')

    assert config['explore'] == 5  # 최고 품질
    assert config['timeout'] == 120000  # 2분

def test_constraint_tuner():
    """제약조건 튜닝 테스트"""
    # 미배정이 많은 결과 시뮬레이션
    vrp_input = {...}
    initial_result = {'unassigned': [...]}

    tuner = ConstraintTuner()
    improved_result = tuner.auto_tune(vrp_input, initial_result)

    # 미배정이 감소했는지 확인
    assert len(improved_result['unassigned']) < len(initial_result['unassigned'])
```

### 3. 통합 테스트 (전체 파이프라인)

```bash
# 실제 VROOM 엔진을 사용한 end-to-end 테스트
./test-wrapper.sh
```

---

## 📊 실전 시나리오 테스트

### 시나리오 1: 2000 jobs, 250 vehicles (실제 데이터)

```python
# tests/test_large_scale.py

def test_real_scenario_2000_jobs():
    """실제 규모 테스트"""
    vrp_input = load_real_data("data/2000_jobs_250_vehicles.json")

    start_time = time.time()

    # v2.0 파이프라인 실행
    result = await optimize_v2(
        vrp_input,
        priority='balanced',
        use_multi_scenario=True,
        auto_tune=True
    )

    duration = time.time() - start_time

    # 성능 검증
    assert duration < 600  # 10분 이내

    # 배정률 검증
    total_jobs = 2000
    unassigned = len(result['unassigned'])
    assignment_rate = (total_jobs - unassigned) / total_jobs

    assert assignment_rate >= 0.95  # 95% 이상 배정

    # 품질 검증
    assert result['analysis']['quality_score']['score'] >= 80
```

---

## 🎯 성능 벤치마크

### v1.0 vs v2.0 비교 목표

| 항목 | v1.0 | v2.0 목표 |
|-----|------|----------|
| 입력 검증 | ❌ 없음 | ✅ Pydantic 자동 검증 |
| 좌표 형식 | 🔸 [lon, lat]만 | ✅ 딕셔너리/문자열 지원 |
| 비즈니스 규칙 | ❌ 수동 적용 | ✅ 자동 적용 |
| 제약조건 튜닝 | ❌ 수동 조정 | ✅ 자동 튜닝 |
| 미배정 사유 | ✅ 있음 | ✅ 개선 (더 상세) |
| 품질 분석 | ❌ 없음 | ✅ 점수/추천 제공 |
| 외부 API | ❌ 없음 | ✅ 날씨/교통/지오코딩 |
| 캐싱 | ❌ 없음 | ✅ Redis 캐싱 |
| 인증 | ❌ 없음 | ✅ API Key + Rate Limit |

---

## 🔄 Git 워크플로우

### 기능별 브랜치 전략

```bash
# Phase 1 작업
git checkout -b feature/phase1-preprocessing
# 작업 완료 후
git add .
git commit -m "Implement Phase 1: Input preprocessing"
git checkout main
git merge feature/phase1-preprocessing

# Phase 2 작업
git checkout -b feature/phase2-control
# ...

# Phase 3 작업
git checkout -b feature/phase3-postprocessing
# ...

# Phase 4 작업
git checkout -b feature/phase4-extensions
# ...
```

### 버전 태그

```bash
# v1.0 태그 (현재)
git tag -a v1.0 -m "VROOM Wrapper v1.0 - Unassigned reason analysis"

# v2.0 태그 (Phase 1-4 완료 후)
git tag -a v2.0 -m "VROOM Wrapper v2.0 - Full control platform"

# 태그 푸시
git push origin --tags
```

---

## 📞 다음 작업

### 옵션 A: Phase 1 구현 시작 (추천)

즉시 시작 가능한 컴포넌트부터 구현:

```bash
# 1. Phase 1 브랜치 생성
git checkout -b feature/phase1-preprocessing

# 2. WRAPPER-IMPLEMENTATION-PLAN.md 열기
# 3. "Phase 1: 입력 전처리 강화" 섹션 코드 복사
# 4. vroom_wrapper.py에 추가
# 5. 테스트 작성 및 실행
# 6. 커밋 및 머지
```

### 옵션 B: GitHub 푸시 (준비 완료)

```bash
# GitHub 저장소 생성 후
git remote add origin https://github.com/YOUR_USERNAME/vroom-wrapper-project.git
git push -u origin main
git push origin --tags
```

### 옵션 C: 현재 v1.0 사용/테스트

```bash
# 서비스 시작
cd /home/shawn/vroom-wrapper-project
docker-compose up -d
python3 vroom_wrapper.py &

# 테스트 실행
./test-wrapper.sh

# 외부 접근 설정 (필요 시)
# EXTERNAL-ACCESS.md 참고
```

---

## 🎓 학습 자료

### VROOM 심화
- [VROOM GitHub](https://github.com/VROOM-Project/vroom)
- [VRP 기초 이론](https://en.wikipedia.org/wiki/Vehicle_routing_problem)

### FastAPI 심화
- [FastAPI 고급 가이드](https://fastapi.tiangolo.com/advanced/)
- [Pydantic 문서](https://docs.pydantic.dev/)

### 최적화 알고리즘
- [OR-Tools VRP 가이드](https://developers.google.com/optimization/routing)
- [VRP 벤치마크](http://vrp.atd-lab.inf.puc-rio.br/index.php/en/)

---

**준비 완료!** 🚀

선택하세요:
1. Phase 1 구현 시작 → 1-2주 작업
2. GitHub 푸시 → 다른 머신에서 사용
3. v1.0 사용/테스트 → 현재 상태로 충분한지 확인

어떤 방향으로 진행하시겠습니까?
