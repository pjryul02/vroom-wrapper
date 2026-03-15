# Roouty Engine vs VROOM Wrapper 비교 분석

## 핵심 발견

**Roouty Engine도 vroom-express를 사용하지 않는다.**
**VROOM 바이너리를 subprocess로 직접 호출한다.**

이것이 가장 중요한 검증 포인트입니다.

---

## 1. 아키텍처 비교

### Roouty Engine (Go)
```
HTTP 요청 (:8000)
    ↓
Go Echo Server
    ↓
┌─── RunDistributeFunc (파이프라인) ───────────────────┐
│                                                      │
│  1. HandleProfiles      → 차량 프로필 결정           │
│  2. HandleCustomMatrix  → OSRM 매트릭스 생성 (병렬)  │
│  3. CalibrateMatrices   → 보정 계수 적용             │
│  4. HandleDistrict      → 지역 기반 필터링           │
│  5. FilterUnreachable   → 도달 불가능 제거           │
│  6. RunWithBound        → VROOUTY 초기 최적화        │
│  7. EqualizeWorkTime    → 작업량 균등화              │
│  8. RunPlan             → 경로별 최적화 (워커 풀)    │
│     ├─ Worker 0 (CPU 0-1) → RunPlanWithSingleRoute   │
│     ├─ Worker 1 (CPU 2-3) → RunPlanWithSingleRoute   │
│     ├─ Worker 2 (CPU 4-5) → RunPlanWithSingleRoute   │
│     └─ Worker 3 (CPU 6-7) → RunPlanWithSingleRoute   │
│  9. appendStepGeometry  → OSRM 경로 형상 + 톨게이트 │
│                                                      │
└──────────────────────────────────────────────────────┘
    ↓
HTTP 응답 (routes + unassigned + summary)
```

### 우리 VROOM Wrapper (Python)
```
HTTP 요청 (:8000)
    ↓
FastAPI Server
    ↓
┌─── Optimize Pipeline ───────────────────────────────┐
│                                                     │
│  Phase 1. Validator         → 입력 검증             │
│  Phase 2. Normalizer        → 데이터 정규화         │
│  Phase 3. BusinessRules     → 비즈니스 룰 적용      │
│  Phase 1.5. MatrixBuilder   → 교통 매트릭스 (TMap)  │
│  Phase 4. Controller        → VROOM 최적화          │
│     └─ HTTP POST :3000      → vroom-express 호출    │
│  Phase 5. Analyzer          → 결과 분석             │
│  Phase 5. Statistics        → 통계 리포트           │
│                                                     │
└─────────────────────────────────────────────────────┘
    ↓
HTTP 응답 (vroom_result + analysis + statistics)
```

---

## 2. VROOM 호출 방식 비교

### Roouty Engine: subprocess 직접 호출 ✅
```go
// pkg/optimizing/vroouty/vroouty.go
cmd := exec.Command(ctx.Config.VrooutyPath(), options...)
// vrootyPath = "/app/out/vroouty"

// stdin으로 JSON 입력
stdin, _ := cmd.StdinPipe()
stdin.Write(requestJSON)
stdin.Close()

// stdout에서 JSON 출력
stdout, _ := cmd.StdoutPipe()
json.NewDecoder(stdout).Decode(&response)
```

**특징:**
- 파일 I/O 없음 (stdin/stdout 파이프)
- CPU 코어 바인딩 (`taskset -c 0-1`)
- 단계별 스레드 수 차등 적용

### 우리 Wrapper: vroom-express HTTP 호출 ❌
```python
# src/control/controller.py
async with httpx.AsyncClient() as client:
    response = await client.post(
        "http://localhost:3000",  # vroom-express
        json=vroom_payload
    )
```

**문제점:**
- 불필요한 HTTP 레이어
- vroom-express가 다시 파일 I/O + spawn
- 이중 JSON 직렬화
- Node.js 의존성

---

## 3. 기능 비교표

| 기능 | Roouty Engine | 우리 Wrapper | 비고 |
|------|:------------:|:-----------:|------|
| **언어** | Go | Python | Go: 성능, Python: 개발 속도 |
| **VROOM 호출** | subprocess (stdin) | HTTP (vroom-express) | Roouty가 효율적 |
| **OSRM 매트릭스** | ✅ 병렬 청킹 | ✅ | Roouty: 75x75 청크 + 32워커 |
| **실시간 교통 API** | ❌ | ✅ TMap/Kakao/Naver | 우리 장점 |
| **매트릭스 보정** | ✅ Calibration | ❌ | Roouty: 방향/속도 계수 적용 |
| **톨게이트 감지** | ✅ OSRM 분석 | ❌ | Roouty: 유료도로 자동 감지 |
| **페리 제외** | ✅ exclude=ferry | ❌ | Roouty: 섬 자동 감지 |
| **워커 풀** | ✅ CPU 바인딩 | ❌ | Roouty: taskset + 코어 할당 |
| **비동기 처리** | ✅ PostgreSQL 큐 | ❌ | Roouty: async=true |
| **작업량 균등화** | ✅ EqualizeWorkTime | ❌ | Roouty: 차량간 작업량 분배 |
| **다중 시나리오** | ❌ | ✅ MultiScenario | 우리 장점 |
| **비즈니스 룰** | △ 기본만 | ✅ 확장 가능 | 우리 장점 |
| **결과 분석** | ❌ | ✅ Phase 5 | 우리 장점 |
| **프로세스 관리** | ✅ ProcessManager | ❌ | Roouty: 프로세스 수명 관리 |
| **메모리 관리** | ✅ sync.Pool | ❌ | Roouty: GC 압력 감소 |
| **데이터베이스** | ✅ PostgreSQL | ❌ Redis만 | Roouty: 작업 이력 영구 저장 |
| **지역 필터링** | ✅ 폴리곤 기반 | ❌ | Roouty: 시도 폴리곤 필터 |
| **커스텀 VROOM** | ✅ vroouty (포크) | ❌ 공식 이미지 | Roouty: C++ 소스 수정 |
| **2단계 최적화** | ✅ 초기 + 경로별 | ❌ 단일 호출 | Roouty: 정교한 2-pass |
| **프로파일 다중** | ✅ 시간대별 프로필 | ❌ | Roouty: 월/화-목/금 분리 |

---

## 4. 파이프라인 깊이 비교

### Roouty Engine (10단계)
```
1. HandleProfiles         → 차량 프로필 결정
2. HandleCustomMatrix     → OSRM 매트릭스 (병렬 청킹)
3. CalibrateMatrices      → 보정 계수 적용
4. HandleDistrict         → 지역 필터링
5. FilterUnreachableJobs  → 도달 불가능 제거
6. RunWithBound           → 초기 최적화 (전체)
7. EqualizeWorkTime       → 작업량 균등화
8. RunPlan                → 경로별 재최적화 (병렬)
9. appendStepGeometry     → 경로 형상 추가
10. extractTollSegments   → 톨게이트 감지
```

### 우리 Wrapper (7단계)
```
1. Validator              → 입력 검증
2. Normalizer             → 정규화
3. BusinessRules          → 비즈니스 룰
4. MatrixBuilder          → 교통 매트릭스 (TMap)
5. Controller.optimize    → VROOM 호출
6. ResultAnalyzer         → 결과 분석
7. StatisticsGenerator    → 통계
```

---

## 5. 성능 최적화 비교

### Roouty Engine의 성능 전략

#### 1. OSRM 청킹 (75x75)
```go
// 250개 위치 → 250x250 매트릭스 = 62,500 셀
// 75x75 청크 = 5,625 셀
// 필요 청크 수 ≈ 12개 → 32워커로 병렬 처리
```

#### 2. 2-Pass 최적화
```
Pass 1: 전체 최적화 (initial_threads=48)
  → "어떤 차량에 어떤 작업?" 결정

Pass 2: 경로별 최적화 (route_threads=8, 병렬)
  → 각 차량의 방문 순서 최적화
  → 워커 풀 (max_workers=12)
  → CPU 코어 바인딩 (taskset)
```

#### 3. 메모리 풀링
```go
sync.Pool로 슬라이스 재사용
→ GC 압력 감소
→ 대규모 요청 (250+ 작업) 안정적
```

#### 4. CPU 코어 바인딩
```
Worker 0 → CPU 0-1 (taskset -c 0,1)
Worker 1 → CPU 2-3 (taskset -c 2,3)
Worker 2 → CPU 4-5 (taskset -c 4,5)
→ L1/L2 캐시 효율성 극대화
```

### 우리 Wrapper의 성능 전략
```
- Redis 캐싱
- 비동기 I/O (asyncio)
- 단일 VROOM 호출
- (아직 부족한 부분 많음)
```

---

## 6. Docker 구성 비교

### Roouty Engine
```yaml
services:
  roouty-engine:        # Go 서버 + VROOUTY 바이너리
    build: .            # 멀티스테이지 (Go + C++)
    ports: ["8000:8000"]

  osrm_car_p1_mon:      # 월요일 프로필 1
    image: osrm-backend:v5.27.1
    ports: ["5010:5000"]

  osrm_car_p2_mon:      # 월요일 프로필 2
    ports: ["5011:5000"]

  # ... 총 10개 OSRM 인스턴스
  # 요일별/시간대별 다른 교통 프로필!
```

**핵심**:
- VROOUTY가 Go 컨테이너 안에 같이 빌드됨
- vroom-express 없음
- OSRM 10개 인스턴스 (요일/시간대별)

### 우리 Wrapper
```yaml
services:
  osrm:                 # OSRM 1개
  vroom:                # vroom-express (불필요!)
  redis:                # 캐시
  wrapper:              # Python 서버
```

---

## 7. Roouty Engine이 우리에게 검증해준 것

### ✅ 직접 호출이 정답
```
Roouty: exec.Command + stdin/stdout
  → vroom-express 사용 안 함
  → 파이프로 직접 통신
  → 성능 최적
```

### ✅ 커스텀 매트릭스 주입이 핵심
```
Roouty: HandleCustomMatrix → OSRM 병렬 호출 → 매트릭스 구성
  → VROOUTY에 matrices 필드로 전달
  → VROOM이 OSRM 호출 스킵
```

### ✅ 2-Pass 최적화가 효과적
```
Pass 1: 전체 배정 (어떤 차에 어떤 작업)
Pass 2: 경로 최적화 (방문 순서)
  → 각 경로를 독립적으로 병렬 최적화
```

### ✅ 워커 풀 + CPU 바인딩이 프로덕션 필수
```
max_workers로 동시 실행 제한
CPU 코어 바인딩으로 캐시 효율
```

---

## 8. 우리가 Roouty Engine에서 배울 점

### 즉시 적용 가능

| 배울 점 | 우선순위 | 난이도 |
|---------|---------|--------|
| **VROOM 직접 호출** (vroom-express 제거) | 🔴 높음 | 쉬움 |
| **stdin/stdout 파이프** (파일 I/O 제거) | 🔴 높음 | 쉬움 |
| **2-Pass 최적화** (초기 + 경로별) | 🟡 중간 | 중간 |
| **OSRM 청킹** (대규모 매트릭스) | 🟡 중간 | 중간 |
| **비동기 작업 큐** (대규모 요청) | 🟡 중간 | 중간 |

### 중장기 적용

| 배울 점 | 우선순위 | 난이도 |
|---------|---------|--------|
| 매트릭스 보정 (Calibration) | 🟢 낮음 | 중간 |
| 톨게이트 감지 | 🟢 낮음 | 중간 |
| 페리/섬 제외 | 🟢 낮음 | 쉬움 |
| 워커 풀 + CPU 바인딩 | 🟡 중간 | 높음 |
| 요일/시간대별 프로필 | 🟡 중간 | 높음 |
| 커스텀 VROOM 포크 | 🔴 높음 | 높음 |

---

## 9. 우리 Wrapper만의 강점

| 우리의 강점 | Roouty에 없는 이유 |
|------------|-------------------|
| **실시간 교통 API** (TMap/Kakao) | Roouty는 OSRM 정적 매트릭스 + 보정 계수 |
| **다중 시나리오 비교** | Roouty는 단일 최적화 |
| **결과 분석/통계** | Roouty는 결과 그대로 반환 |
| **비즈니스 룰 확장** | Roouty는 하드코딩 |
| **하이브리드 매트릭스** | Roouty는 OSRM Only |

---

## 10. 핵심 결론

### Roouty Engine의 아키텍처 선택

```
┌────────────────────────────────────────┐
│     ❌ vroom-express 사용 안 함        │
│     ✅ VROOM 바이너리 직접 호출         │
│     ✅ stdin/stdout 파이프 통신         │
│     ✅ CPU 코어 바인딩                  │
│     ✅ 2-Pass 최적화                    │
│     ✅ 커스텀 VROOM 포크 (vroouty)      │
└────────────────────────────────────────┘
```

### 우리에게 의미하는 것

1. **vroom-express 제거는 필수** - 프로덕션 시스템에서 이미 검증됨
2. **stdin/stdout 파이프가 최적** - 파일 I/O보다 효율적
3. **2-Pass 최적화 도입 고려** - 대규모 문제에서 품질 향상
4. **실시간 교통은 우리의 차별점** - Roouty도 못하는 것

### 즉시 해야 할 일

```
1. vroom-express 제거 → subprocess 직접 호출
2. stdin/stdout 파이프 구현
3. 2-Pass 최적화 구조 설계
4. OSRM 청킹 도입 (대규모 매트릭스)
```

---

## 부록: Roouty Engine 코드 위치

| 파일 | 역할 | 줄 수 |
|------|------|------|
| `pkg/optimizing/vroouty/vroouty.go` | VROOM 바이너리 실행 | ~200 |
| `pkg/optimizing/vroouty/request.go` | 요청 스키마 | ~300 |
| `pkg/optimizing/vroouty/response.go` | 응답 스키마 | ~200 |
| `pkg/features/distribute/run.go` | 메인 파이프라인 | ~500 |
| `pkg/features/distribute/custom_matrix.go` | 매트릭스 구성 | ~200 |
| `pkg/routing/osrm/osrm.go` | OSRM 통신 | ~700 |
| `pkg/config/config.go` | 설정 관리 | ~400 |
| `pkg/services/process_manager.go` | 프로세스 관리 | ~300 |
| **총계** | | **~2,800줄 (핵심만)** |
