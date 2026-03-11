# VROOM Wrapper v3.1 — 기술 아키텍처 문서

**최종 업데이트**: 2026-03-02
**대상**: vroom-wrapper-project (`src/`)
**기준**: v3.0 Synthesis + 2-Pass/OSRM 매트릭스 사전계산 (v3.1)

---

## 목차

1. [시스템 아키텍처](#1-시스템-아키텍처)
2. [모듈 구조](#2-모듈-구조)
3. [처리 파이프라인: /optimize](#3-처리-파이프라인-optimize)
4. [처리 파이프라인: /dispatch (HGLIS)](#4-처리-파이프라인-dispatch-hglis)
5. [핵심 알고리즘 상세](#5-핵심-알고리즘-상세)
6. [VROOM 엔진 내부 참조](#6-vroom-엔진-내부-참조)
7. [OSRM 참조](#7-osrm-참조)
8. [비동기 모드](#8-비동기-모드)
9. [정확도 한계와 향후 개선](#9-정확도-한계와-향후-개선)

---

## 1. 시스템 아키텍처

### 1.1 Docker 구성

```
docker-compose.v3.yml
├── osrm      (ghcr.io/project-osrm/osrm-backend)       → :5000
├── valhalla  (ghcr.io/gis-ops/docker-valhalla/valhalla) → :8002
├── redis     (redis:7-alpine)                           → :6379
└── wrapper   (Dockerfile.v3 멀티스테이지)                 → :8000
    ├── Stage 1: vroom-local:latest → VROOM 바이너리 추출
    └── Stage 2: python:3.11-slim + VROOM + FastAPI
```

v2.0까지 4컨테이너(OSRM + VROOM + vroom-express + Wrapper)였으나,
v3.0에서 vroom-express 제거 → **VROOM 바이너리 직접 호출**로 3컨테이너 구성.
v3.1에서 **Valhalla 추가** → 4컨테이너 구성 (OSRM 대체/보완, time-dependent routing).

### 1.2 호출 흐름

```
클라이언트 ──HTTP──→ FastAPI (Wrapper :8000)
                         │
                         ├─ stdin/stdout ──→ VROOM 바이너리 (subprocess)
                         ├─ HTTP ──→ OSRM (:5000)
                         ├─ HTTP ──→ Valhalla (:8002)
                         └─ TCP ──→ Redis (:6379)
```

VROOM은 HTTP 서버가 아님. Wrapper가 `asyncio.create_subprocess_exec()`로 직접 실행하고 JSON을 stdin으로 보내고 stdout에서 결과를 받음.

### 1.3 v2.0 → v3.0 변경

| 구분 | v2.0 | v3.0+ |
|------|------|-------|
| VROOM 호출 | HTTP → vroom-express → VROOM | stdin/stdout → VROOM 직접 |
| 최적화 | 단일 Pass | **2-Pass** (배정 + 경로최적화) |
| 매트릭스 | VROOM이 OSRM 직접 호출 | **Wrapper가 1회 사전계산** → VROOM에 주입 |
| 도달불가 처리 | 없음 | **매트릭스 기반 사전 필터링** |
| 대규모 매트릭스 | 단일 요청 | **75×75 청킹 + 8 워커 병렬** |
| 컨테이너 | 4개 | 3개 (v3.0) → 4개 (v3.1, +Valhalla) |

---

## 2. 모듈 구조

```
src/
├── main_v3.py              # FastAPI 앱, 라우터 등록
├── config.py               # 환경변수 30+ 관리
├── api_models.py           # Pydantic 요청 모델 (Distribute, Optimize, Matrix)
│
├── api/                    # 엔드포인트 라우터
│   ├── distribute.py       # POST /distribute (VROOM 호환)
│   ├── optimize.py         # POST /optimize, /optimize/basic, /optimize/premium
│   ├── dispatch.py         # POST /dispatch (HGLIS)
│   ├── jobs.py             # GET /jobs/{job_id} (비동기 진행률)
│   ├── matrix.py           # POST /matrix/build
│   ├── map_matching.py     # POST /map-matching/match, /validate
│   ├── valhalla.py         # /valhalla/* 엔드포인트 (OSRM 병렬 비교)
│   └── health.py           # GET /, /health, DELETE /cache/clear
│
├── core/                   # 공통 인프라
│   ├── auth.py             # API Key 인증 + Rate Limiting
│   └── dependencies.py     # 싱글턴 컴포넌트 관리
│
├── preprocessing/          # Phase 1: 전처리
│   ├── preprocessor.py     # 통합 전처리 오케스트레이터
│   ├── validator.py        # 입력 검증
│   ├── normalizer.py       # 필드 정규화
│   ├── business_rules.py   # VIP/긴급/지역 비즈니스 규칙
│   ├── unreachable_filter.py  # 도달불가 사전 필터링
│   ├── vroom_matrix_preparer.py  # OSRM 매트릭스 사전계산 + VROOM 주입
│   ├── valhalla_matrix.py  # Valhalla 매트릭스 계산
│   ├── chunked_matrix.py   # OSRM 75×75 청킹 매트릭스
│   └── matrix_builder.py   # 실시간 교통 매트릭스 (TMap/Kakao/Naver)
│
├── control/                # Phase 2: 최적화 제어
│   ├── controller.py       # OptimizationController (2-Pass/시나리오/재시도)
│   ├── vroom_config.py     # BASIC/STANDARD/PREMIUM 설정 생성
│   ├── constraint_tuner.py # 제약 완화 6단계 자동 재시도
│   └── multi_scenario.py   # 다중 시나리오 병렬 실행
│
├── optimization/           # 최적화 엔진
│   ├── two_pass.py         # 2-Pass 최적화 (Pass1 배정 + Pass2 경로)
│   └── vroom_executor.py   # VROOM 바이너리 직접 호출
│
├── postprocessing/         # Phase 3: 후처리
│   ├── constraint_checker.py  # 미배정 사유 역추적 분석
│   ├── analyzer.py         # 품질 분석 (0~100 점수)
│   └── statistics.py       # 차량/비용/시간/효율 통계
│
├── hglis/                  # HGLIS 배차 전용
│   ├── models.py           # Pydantic 모델 (HglisJob, HglisVehicle, C1~C8)
│   ├── dispatcher.py       # HGLIS 배차 오케스트레이터
│   ├── skill_encoder.py    # C4/C7/C8/소파 → VROOM skills 인코딩
│   ├── vroom_assembler.py  # HGLIS → VROOM JSON 변환
│   ├── fee_validator.py    # C2 설치비 하한 검증
│   ├── monthly_cap.py      # C6 월상한 검증
│   ├── joint_dispatch.py   # 합배차 처리
│   ├── region_splitter.py  # 권역 분할
│   ├── time_converter.py   # 시간 변환
│   └── validator.py        # HGLIS 입력 검증
│
├── map_matching/           # GPS 궤적 도로 매칭
│   ├── engine.py           # OSRM 기반 Map Matcher
│   ├── models.py           # 맵 매칭 요청/응답 모델
│   ├── config.py           # 맵 매칭 설정
│   ├── geometry.py         # 기하학 유틸리티
│   └── parameters.py       # 파라미터 정의
│
├── services/               # 공통 서비스
│   └── job_manager.py      # 비동기 작업 진행률 관리
│
└── extensions/             # 확장 모듈
    └── cache_manager.py    # Redis/인메모리 캐시
```

---

## 3. 처리 파이프라인: /optimize

`/optimize` (STANDARD), `/optimize/basic` (BASIC), `/optimize/premium` (PREMIUM) 공통 흐름.

```
요청 수신
  │
  ├─ [캐시 확인] (STANDARD만, use_cache=true 시)
  │    └─ cache hit → 즉시 반환
  │
  ├─ Phase 1: 전처리 (preprocessor.py)
  │    ├─ 1-1. InputValidator: 필드/타입/범위 검증
  │    ├─ 1-2. InputNormalizer: 기본값, 좌표, 시간 정규화
  │    ├─ 1-3. BusinessRuleEngine: VIP/긴급/지역 규칙 적용
  │    └─ 1-4. HybridMatrixBuilder: (선택) 실시간 교통 매트릭스
  │
  ├─ Phase 2: 최적화 (controller.py)
  │    ├─ 2-1. VROOMConfigManager: 레벨별 설정 생성
  │    │        BASIC: threads=2, explore=1
  │    │        STANDARD: threads=4, explore=5
  │    │        PREMIUM: threads=4, explore=5, multi-scenario
  │    │
  │    ├─ 2-2. UnreachableFilter: 매트릭스 기반 도달불가 제거
  │    │
  │    ├─ 2-3. 최적화 실행 (택 1)
  │    │    ├─ PREMIUM: MultiScenario → 3개 시나리오 병렬 → 최적 선택
  │    │    ├─ STANDARD/BASIC (jobs≥10): TwoPassOptimizer
  │    │    └─ STANDARD/BASIC (jobs<10): 단일 VROOM 호출
  │    │
  │    └─ 2-4. (STANDARD) 자동 재시도: 미배정 있으면 제약 완화 6단계
  │
  ├─ Phase 3: 후처리
  │    ├─ 3-1. ConstraintChecker: 미배정 사유 역추적
  │    ├─ 3-2. Analyzer: 품질 점수 (STANDARD/PREMIUM만)
  │    └─ 3-3. StatisticsGenerator: 통계 (STANDARD/PREMIUM만)
  │
  └─ [캐시 저장] (STANDARD만)
```

---

## 4. 처리 파이프라인: /dispatch (HGLIS)

HGLIS 전용 파이프라인. 비즈니스 모델(기사, 오더, 제품, 스케줄) → VROOM 변환 → 최적화 → HGLIS 응답.

### 4.1 전체 흐름

```
POST /dispatch (HglisDispatchRequest)
  │
  ├─ Step 1: 검증
  │    ├─ Pydantic 모델 검증 (좌표, 권역코드, 제품)
  │    └─ 기본 정합성 확인
  │
  ├─ Step 2: 합배차 전처리
  │    ├─ 2인 오더 탐색
  │    └─ 합배차 job 복제 (Phase 3 활성화 시)
  │
  ├─ Step 3: 스킬 인코딩 (SkillEncoder)
  │    ├─ C4 기능도 → skill 1~4
  │    ├─ C7 신제품 → skill 100+
  │    ├─ C8 미결이력 → skill 300+
  │    └─ 소파 → skill 500
  │
  ├─ Step 4: 권역 분할
  │    ├─ strict: 기사-오더 권역 정확 일치
  │    ├─ flexible: 인접 권역 허용 (미배정 재시도)
  │    └─ ignore: 전체 매칭
  │
  ├─ Step 5: 권역별 VROOM 실행
  │    각 권역에 대해:
  │    ├─ VroomAssembler: HGLIS → VROOM JSON 변환
  │    │    ├─ Job: CBM×100→delivery, time_windows, skills, service+setup
  │    │    ├─ Vehicle: CBM×100→capacity, skills, time_window, breaks, max_tasks
  │    │    └─ max_tasks 동적: min(설정값, ceil(오더/기사)+2)
  │    │
  │    ├─ VroomMatrixPreparer: OSRM 매트릭스 1회 사전계산
  │    │    ├─ 모든 고유좌표 수집 → OSRM Table API 1회 호출
  │    │    ├─ jobs에 location_index, vehicles에 start_index/end_index 추가
  │    │    └─ matrices.car.{durations, distances} 주입
  │    │
  │    └─ OptimizationController.optimize()
  │         ├─ UnreachableFilter: 매트릭스 기반 도달불가 제거
  │         ├─ 2-Pass 최적화 (활성화 시, jobs≥10)
  │         │    ├─ Pass 1: 전체 배정 (threads=16)
  │         │    └─ Pass 2: 경로별 재최적화 (threads=4, 병렬)
  │         └─ 자동 재시도 (미배정 시)
  │
  ├─ Step 6: 결과 변환
  │    ├─ VROOM route → DispatchResult (order_id, driver_id, sequence, arrival)
  │    ├─ 기사별 요약 (assigned_count, total_fee, distance_km)
  │    └─ 미배정 사유 (constraint, reason)
  │
  ├─ Step 7: C2/C6 검증
  │    ├─ C2: 일일수익(설치비+거리비) ≥ 하한 → warning
  │    └─ C6: 월누적+오늘배정 vs 월상한 → warning/over
  │
  └─ HglisDispatchResponse
```

### 4.2 HGLIS 제약 → VROOM 매핑

| 코드 | 제약 | VROOM 매핑 방식 | 구현 파일 |
|------|------|----------------|----------|
| C1 | 합배차 | job 복제 + 2인팀 우선순위 | dispatcher.py |
| C2 | 설치비 하한 | 사후 검증 (warning) | fee_validator.py |
| C3 | 시간대 | time_windows 변환 | vroom_assembler.py |
| C4 | 기능도 | skills (1~4) | skill_encoder.py |
| C5 | CBM 용량 | capacity/delivery (CBM×100) | vroom_assembler.py |
| C6 | 월상한 | 사후 검증 (warning) | monthly_cap.py |
| C7 | 신제품 | skills (100+) | skill_encoder.py |
| C8 | 미결이력 | skills (300+, 역방향) | skill_encoder.py |

### 4.3 스킬 인코딩 상세 (SkillEncoder)

VROOM의 skills은 정수 배열이고, job이 가진 skill을 vehicle도 가져야 배정 가능 (`job.skills ⊆ vehicle.skills`).

**C4 기능도 (skill 1~4)**
```
등급:  S=4  A=3  B=2  C=1
오더: required_grade 중 최고값 1개만 skill로 부여
기사: 자기 등급 이하 전부 (S기사 → [1,2,3,4], B기사 → [1,2])
→ B등급 필요 오더(skill [2]) = S기사(skills [1,2,3,4]) 배정 가능
→ B등급 필요 오더(skill [2]) = C기사(skills [1]) 배정 불가
```

**C7 신제품 (skill 100+)**
```
각 신제품 model_code → 고유 skill_id 동적 할당 (100, 101, 102, ...)
오더: 신제품 포함 시 해당 skill 부여
기사: new_product_restricted=false면 전체 신제품 skill 부여
      new_product_restricted=true면 신제품 skill 미부여 → 배정 불가
```

**C8 미결이력 (skill 300+, 역방향)**
```
각 회피 model_code → 고유 skill_id 동적 할당 (300, 301, 302, ...)
오더: 해당 모델 포함 시 skill 부여
기사: avoid_models에 없는 모델만 skill 부여
→ 기사가 REF-001 회피 && 오더에 REF-001 포함 → skill 불일치 → 배정 불가
```

---

## 5. 핵심 알고리즘 상세

### 5.1 2-Pass 최적화 (two_pass.py)

Roouty Engine (Go) `RunWithBound` 패턴의 Python 비동기 구현.

**배경**: VROOM은 단일 최적화에서 배정과 경로 순서를 동시에 결정. 대규모 문제에서 경로 순서 품질이 떨어질 수 있음.

**해결**: 2단계로 분리.

```
Pass 1: 전체 배정 (어떤 차량에 어떤 작업)
  - 높은 스레드 (기본 16) → 넓은 탐색
  - 결과: 차량별 작업 목록

Pass 2: 경로별 순서 최적화 (경로 내 방문 순서)
  - 차량별 독립 → ProcessPoolExecutor 병렬
  - 낮은 스레드 (기본 4) → 작은 문제에 집중
  - 매트릭스에서 서브매트릭스 추출 → 인덱스 재매핑
```

**서브매트릭스 추출** (`_extract_sub_matrix`):
```
Pass 1 매트릭스: 14×14 (전체 좌표)
Route 1 사용 좌표: [0, 3, 5, 7, 12] (차량 + 작업 5개)
→ 서브매트릭스: 5×5로 추출
→ 인덱스 재매핑: 0→0, 3→1, 5→2, 7→3, 12→4
→ jobs의 location_index, vehicles의 start_index/end_index 갱신
```

**활성화 조건**: `TWO_PASS_ENABLED=true` + jobs ≥ 10

### 5.2 OSRM 매트릭스 사전계산 (vroom_matrix_preparer.py)

**문제**: VROOM에 좌표만 넘기면 VROOM이 매 호출마다 OSRM에 거리/시간 요청.
2-Pass에서 Pass 2가 경로마다 OSRM 재호출 → 비효율.

**해결**: Wrapper에서 OSRM 1회 호출 → 매트릭스를 VROOM 입력에 주입.

```python
# 1. 모든 고유 좌표 수집
coords = set()
for v in vehicles: coords.add(v.start); coords.add(v.end)
for j in jobs: coords.add(j.location)

# 2. OSRM Table API 1회 호출
matrix = await osrm_chunked_matrix.build_matrix(list(coords))

# 3. 좌표 → 인덱스 매핑 (소수점 6자리 반올림)
coord_to_idx = {round_coord(c): i for i, c in enumerate(coords)}

# 4. VROOM 입력에 주입
for job in jobs:
    job["location_index"] = coord_to_idx[round_coord(job["location"])]
vrp_input["matrices"] = {"car": {"durations": [...], "distances": [...]}}
```

**효과**:
- 2-Pass에서 OSRM 재호출 없음
- UnreachableFilter가 매트릭스 사용 가능
- 대규모(75+ 좌표)는 75×75 청킹 + 8 워커 병렬

### 5.3 도달불가 필터 (unreachable_filter.py)

OSRM 매트릭스에서 `null` 또는 임계값(43,200초=12시간) 초과인 경우 도달 불가로 판정.

```
모든 차량에서 job까지 양방향(가기+돌아오기) 도달 불가
  → VROOM 호출 전 제거
  → unassigned에 "unreachable" 사유로 추가
```

**왜 필요**: VROOM에 도달불가 좌표를 넣으면 라우팅 에러 발생하거나 전체 최적화 실패.

### 5.4 미배정 사유 역추적 (constraint_checker.py)

**문제**: VROOM은 미배정 작업이 "왜" 미배정인지 알려주지 않음. `unassigned: [{id: 103}]` 만 반환.

**해결**: Wrapper가 원본 입력과 결과를 비교 분석하여 사유 추론.

**검사 순서** (필터 체이닝):
```
1. Skills (Hard Constraint)
   - job.skills ⊆ vehicle.skills 검사
   - 모든 차량에서 skills 부재 → "skills" 사유
   - 정확도: 100% (단순 집합 비교)

2. Capacity (Hard Constraint)
   - job.delivery[i] ≤ vehicle.capacity[i] (모든 차원)
   - 모든 호환 차량에서 용량 초과 → "capacity" 사유
   - 정확도: 100% (단순 숫자 비교)

3. Time Window (Soft Constraint)
   - job.time_windows와 vehicle.time_window 겹침 확인
   - 겹침 공식: start1 ≤ end2 AND end1 ≥ start2
   - 정확도: ~95% (실제 경로 이동시간 미고려)

4. Max Tasks
   - 이미 배정된 작업 수 추정
   - 정확도: ~90% (정확한 배정 수는 VROOM만 앎)

5. Complex Constraint
   - 위 4가지 모두 통과했지만 미배정 → "complex_constraint"
   - 가능한 실제 원인: 경로 효율성, Break 제약, 우선순위 조합
   - 정확도: ~70% (VROOM 최적화 로직은 블랙박스)
```

**정확도 요약**:

| 제약 타입 | 정확도 | 이유 |
|-----------|--------|------|
| Skills | 100% | 단순 집합 비교 |
| Capacity | 100% | 단순 숫자 비교 |
| Time Window | 95% | 겹침 확인 가능, 이동시간 미고려 |
| Max Tasks | 90% | 배정 수 추정 가능 |
| Complex | 70% | VROOM 최적화 블랙박스 |

### 5.5 제약 완화 자동 재시도 (constraint_tuner.py)

미배정 작업이 있으면 제약을 단계적으로 완화하며 재시도.

```
단계 1: time_window 10% 확장
단계 2: time_window 20% 확장
단계 3: max_tasks +2 증가
단계 4: time_window 30% + max_tasks +2
단계 5: priority 1단계 낮추기
단계 6: time_window 50% + max_tasks +4
```

각 단계 결과가 이전보다 나으면(미배정 감소 or 비용 감소) 채택.
최종 결과에 `relaxation_metadata` 첨부 (어떤 완화를 적용했는지).

---

## 6. VROOM 엔진 내부 참조

### 6.1 VROOM 실행 인자

```bash
vroom -i input.json \
  -r osrm \                    # 라우터 (osrm/ors/valhalla)
  -a osrm:5000 \               # 라우터 주소
  -t 4 \                       # 스레드 수
  -x 5 \                       # 탐색 레벨 (0~5)
  -g                           # geometry 포함
```

| 인자 | 설명 | 기본값 |
|------|------|--------|
| `-t` | 스레드 수. 높을수록 탐색 넓지만 CPU 사용 증가 | 4 |
| `-x` | 탐색 레벨 (0=빠른결과, 5=깊은탐색). 품질↑ 시간↑ | 5 |
| `-g` | 경로 geometry(polyline) 포함. 없으면 거리=null | off |
| `-c` | Plan Mode: 최적화 없이 제약 위반만 체크 | off |

### 6.2 Hard vs Soft Constraint

VROOM의 제약은 두 종류:

**Hard Constraint** — 절대 위반 불가, 위반 시 `unassigned`로 처리:
- Skills: `job.skills ⊆ vehicle.skills`
- Capacity: 모든 차원에서 `load ≤ capacity`
- Shipment Precedence: pickup 반드시 delivery 전

**Soft Constraint** — 위반 가능, `violations` 배열에 기록:
- Time Windows: DELAY (지각), LEAD_TIME (조기도착)
- Max Travel Time: 차량 최대 이동시간 초과
- Max Distance: 차량 최대 이동거리 초과
- Missing Break: 휴식시간 미확보

### 6.3 VROOM Violations 10종

```
LEAD_TIME         조기 도착 (시간 윈도우 시작 전)
DELAY             지각 (시간 윈도우 종료 후)
LOAD              적재량 초과
MAX_TASKS         최대 작업 수 초과
SKILLS            스킬 미보유
PRECEDENCE        수거-배송 순서 위반
MISSING_BREAK     휴식시간 미확보
MAX_TRAVEL_TIME   최대 이동시간 초과
MAX_LOAD          최대 적재량 초과
MAX_DISTANCE      최대 이동거리 초과
```

**Violations 3계층 보고 구조**:
```json
{
  "summary": {"violations": [...]},          // 전체 요약
  "routes": [{
    "violations": [...],                     // 경로 레벨
    "steps": [{
      "violations": [{"cause": 2, "duration": 120}]  // 단계 레벨
    }]
  }]
}
```

### 6.4 탐색 레벨 (-x) 상세

| 레벨 | 탐색 강도 | 사용 시나리오 |
|------|----------|-------------|
| 0 | 최소 — 빠른 초기 해만 | 실시간/프리뷰 |
| 1 | 가벼운 로컬 서치 | 소규모 (< 20 jobs) |
| 2-3 | 기본 메타휴리스틱 | 중규모 |
| 4 | 깊은 탐색 | 대규모 |
| 5 | 최대 탐색 — 시간 많이 소요 | 품질 최우선 |

환경변수 `VROOM_EXPLORATION`으로 설정. BASIC=1, STANDARD=5, PREMIUM=5.

---

## 7. OSRM 참조

### 7.1 OSRM API 직접 사용

Wrapper가 내부적으로 호출하지만, 디버깅 시 직접 사용 가능.

**Route (경로 탐색)**
```bash
curl "http://localhost:5000/route/v1/driving/126.9780,37.5665;127.0276,37.4979?overview=full&geometries=geojson"
```

**Table (거리/시간 매트릭스)**
```bash
curl "http://localhost:5000/table/v1/driving/126.9780,37.5665;127.0276,37.4979;127.0594,37.5140"
```
→ `durations` NxN 배열 + `distances` NxN 배열

**Nearest (최근접 도로 스냅)**
```bash
curl "http://localhost:5000/nearest/v1/driving/126.9780,37.5665?number=3"
```

### 7.2 OSRM 알고리즘

| 알고리즘 | 특징 | 설정 |
|---------|------|------|
| MLD (Multi-Level Dijkstra) | 기본, 범용적 | `osrm-contract` → `osrm-routed --algorithm mld` |
| CH (Contraction Hierarchies) | 대규모 Table API에 유리 | `osrm-contract` → `osrm-routed --algorithm ch` |

현재 설정: MLD (기본). 대규모(500+ 좌표) 매트릭스에서 CH 전환 고려 가능.

### 7.3 OSRM 성능 옵션

```bash
# docker-compose.v3.yml의 osrm 서비스
osrm-routed \
  --algorithm mld \
  --max-table-size 10000 \    # 매트릭스 최대 크기 (기본 상향)
  /data/south-korea-latest.osrm
```

### 7.4 프로파일 변경

기본은 `car.lua` (자동차). 자전거/도보로 변경 시:
```bash
osrm-extract -p /opt/bicycle.lua south-korea-latest.osm.pbf
osrm-partition south-korea-latest.osrm
osrm-customize south-korea-latest.osrm
```

---

## 8. 비동기 모드

### 8.1 흐름

```
POST /dispatch?async=true
  → 즉시 반환: {"job_id": "uuid", "status": "queued", "poll_url": "/jobs/{job_id}"}
  → 백그라운드 실행: FastAPI BackgroundTasks

GET /jobs/{job_id}
  → 진행률 반환: {"status": "processing", "progress": {"stage": "optimizing", "percentage": 40}}
  → 완료 시: {"status": "completed", "result": {...}}
```

### 8.2 진행 단계 (JobManager)

| stage | % | 설명 |
|-------|---|------|
| queued | 0 | 대기 중 |
| validating | 10 | 입력 검증 |
| preprocessing | 20 | 전처리 (매트릭스, 필터) |
| optimizing | 40 | Pass 1 최적화 |
| optimizing_pass2 | 60 | Pass 2 최적화 |
| retry_relaxation | 75 | 제약 완화 재시도 |
| postprocessing | 90 | 후처리 (C2/C6) |
| completed | 100 | 완료 |
| failed | - | 실패 |

### 8.3 구현

- 인메모리 저장 (Redis 미사용) — 단일 인스턴스 전제
- TTL: 2시간 후 자동 삭제
- 폴링 권장 간격: 1~2초

---

## 9. 정확도 한계와 향후 개선

### 9.1 현재 한계

| 항목 | 한계 | 원인 |
|------|------|------|
| Time Window 정확도 | ~95% | 실제 경로 이동시간 미고려 (겹침만 확인) |
| Max Tasks 정확도 | ~90% | VROOM이 실제로 배정한 작업 수를 모름 |
| Complex Constraint | ~70% | VROOM 최적화 로직이 블랙박스 |
| Break 제약 | 미추적 | Wrapper에서 Break 위반 분석 미구현 |
| 비동기 Job | 인메모리 | 서버 재시작 시 작업 유실 |

### 9.2 정확도 개선 전략 (향후)

**전략 3: 하이브리드 (VROOM 디버그 로그 + Wrapper)**

VROOM C++ `input.cpp`에 호환성 매트릭스 덤프 기능 추가:
```cpp
void Input::log_compatibility_matrix() {
    // vehicle_id × job_id → 비호환 이유 (skills/capacity/tw/...) 출력
    // /tmp/vroom_compatibility.json 에 저장
}
```
Wrapper가 이 로그를 읽으면 정확도 95%+ 달성 가능.
→ VROOM 소스 수정 필요하므로 향후 검토.

**OSRM 통합 Time Reachability**

```python
def check_time_reachability(vehicle, job, osrm_client):
    route = osrm_client.route([v.start, j.location])
    travel_time = route['routes'][0]['duration']
    arrival = v.time_window[0] + travel_time
    return job.time_windows[0][0] <= arrival <= job.time_windows[0][1]
```
→ Time Window 정확도 95% → 99% 가능.

### 9.3 Roouty Engine에서 미도입 기능

| 기능 | 설명 | 난이도 |
|------|------|--------|
| OSRM 캘리브레이션 (0.65) | 예측 거리에 보정계수 적용 | 낮음 |
| 시간대별 OSRM 프로필 | 출퇴근 시간대별 다른 라우팅 | 높음 |
| CPU 코어 바인딩 | VROOM 프로세스 CPU 친화성 | 낮음 |
| 동적 재최적화 | 실시간 주문 추가 후 incremental update | 높음 |
| 커스텀 비용 함수 | distance×0.5 + time×0.3 + toll×0.2 혼합 | 중간 |

---

## 부록: 환경변수 핵심 목록

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `USE_DIRECT_CALL` | true | VROOM 바이너리 직접 호출 |
| `VROOM_BINARY_PATH` | /usr/local/bin/vroom | 바이너리 경로 |
| `VROOM_THREADS` | 4 | 기본 스레드 |
| `VROOM_EXPLORATION` | 5 | 탐색 레벨 (0~5) |
| `TWO_PASS_ENABLED` | true | 2-Pass 최적화 활성화 |
| `TWO_PASS_INITIAL_THREADS` | 16 | Pass 1 스레드 |
| `TWO_PASS_ROUTE_THREADS` | 4 | Pass 2 스레드 |
| `MATRIX_PREP_ENABLED` | true | OSRM 매트릭스 사전계산 |
| `UNREACHABLE_FILTER_ENABLED` | true | 도달불가 필터 |
| `UNREACHABLE_THRESHOLD` | 43200 | 도달불가 임계값 (초) |
| `OSRM_URL` | http://osrm:5000 | OSRM 주소 |
| `OSRM_CHUNK_SIZE` | 75 | 청킹 크기 |
| `OSRM_MAX_WORKERS` | 8 | 청킹 병렬 워커 |
| `REDIS_URL` | redis://redis:6379 | Redis 주소 |
