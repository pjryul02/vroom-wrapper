# VROOM Wrapper 퀵 가이드 — "래퍼가 뭘 하는 거야?"

> **대상**: 래퍼를 처음 보는 사람, 또는 코드 구조를 빠르게 훑고 싶은 사람
> **확장 풀버전**: [`docs/TECHNICAL-ARCHITECTURE.md`](docs/TECHNICAL-ARCHITECTURE.md) — 알고리즘 상세, VROOM 내부, OSRM/Valhalla 참조까지 포함

---

## 한 줄 요약

**VROOM은 최적화만 한다. 나머지 전부(검증, 변환, 분석, 통계)가 래퍼의 일이다.**

```
클라이언트 JSON ──→ [래퍼: 전처리] ──→ VROOM 바이너리 ──→ [래퍼: 후처리] ──→ 분석된 응답 JSON
```

---

## 코드 구조 — 6개 층

```
src/
├── api/                ← 1층. 엔드포인트 (요청 수신, 인증, 라우팅)
├── preprocessing/      ← 2층. 전처리 (VROOM이 먹을 수 있게 가공)
├── control/            ← 3층. 최적화 제어 (전략 결정)
├── optimization/       ← 4층. VROOM 실행
├── postprocessing/     ← 5층. 후처리 (결과 분석 + 통계)
└── hglis/              ← 6층. HGLIS 전용 변환기 (포맷 통번역)
```

추가:
- `map_matching/` — GPS 궤적 도로 매칭 (별도 기능)
- `core/` — 인증, 의존성 주입, Redis 캐시
- `services/` — 비동기 Job 관리

---

## 1층. API — "문 열어주는 역할"

```
src/api/
├── distribute.py   ← POST /distribute (인증 불필요, 빠른 배분)
├── optimize.py     ← POST /optimize, /optimize/basic, /optimize/premium
├── dispatch.py     ← POST /dispatch (HGLIS 가전배송 전용)
├── valhalla.py     ← POST /valhalla/distribute, /valhalla/optimize
├── map_matching.py ← POST /map-matching/match
├── matrix.py       ← POST /matrix (거리 행렬 직접 조회)
├── health.py       ← GET /health
└── jobs.py         ← GET /jobs/{id} (비동기 진행률 조회)
```

각 엔드포인트는 인증 확인 후 해당 파이프라인으로 넘긴다.
`/optimize` 계열과 `/dispatch`는 `X-API-Key` 헤더 필수 → `core/auth.py`에서 검증.

---

## 2층. 전처리 — "VROOM이 먹을 수 있게"

VROOM은 순수 수학 엔진이라 비즈니스 개념(VIP, 지역, 기능도)을 모른다. 래퍼가 번역해준다.

### 파이프라인 순서 (`preprocessing/preprocessor.py`가 오케스트레이션)

```
입력 JSON
  │
  ▼ validator.py
① 검증          — 좌표 범위, ID 중복, 필수 필드 / 한국 경계 벗어나면 여기서 422 반환
  │
  ▼ normalizer.py
② 정규화         — 기본값 채우기, 포맷 통일
  │               end 없으면 start로 복귀
  │               ISO 시간("09:00") → Unix timestamp
  │               service 없으면 300초
  │
  ▼ business_rules.py
③ 비즈니스 규칙  — 비즈니스 개념 → VROOM skills/time_windows 번호로 인코딩
  │               VIP 고객 → skill 10000
  │               긴급 배송 → skill 10001
  │               서울 지역 → skill 20000
  │
  ▼ unreachable_filter.py
④ 도달 불가 제거 — OSRM 매트릭스로 12시간 넘는 작업 사전 제거
  │               "이 작업은 어떤 차량도 도달 못 함" → VROOM에 넘기지 않음
  │
  ▼ vroom_matrix_preparer.py  (또는 valhalla_matrix.py)
⑤ 매트릭스 준비  — 모든 좌표 쌍의 거리/시간 사전 계산
                  chunked_matrix.py: 75×75 청킹
                  matrix_builder.py: 8워커 병렬 호출
                  → VROOM JSON에 matrices 필드로 주입
                  → 이후 VROOM이 OSRM을 재호출하지 않음 (속도 핵심)
```

**Valhalla 분기**: `/valhalla/*` 엔드포인트는 ⑤단계에서 `vroom_matrix_preparer` 대신 `valhalla_matrix.py`를 사용한다. OSRM vs Valhalla 차이는 매트릭스 계산에만 있고, 나머지 파이프라인은 동일.

---

## 3층. 최적화 제어 — "어떻게 돌릴까"

VROOM을 한 번만 돌리는 게 아니라 상황에 따라 전략을 바꾼다.

### 2-Pass 최적화 (`optimization/two_pass.py`)

```
Pass 1: "누가 어디 갈지" — 배정 문제 (스레드 16, 탐색 깊이 5)
  │ 차량별 배정 결과 확정
  ▼
Pass 2: "어떤 순서로 갈지" — 경로 최적화 (차량별 병렬, 스레드 4)
```

왜 2번? — 전체를 한 번에 돌리면 탐색 공간 폭발. 배정과 순서를 분리하면 더 좋은 결과.

### 자동 재시도 (`control/constraint_tuner.py`)

미배정이 많으면 제약을 단계적으로 완화:

```
1단계: 시간창 ×1.2 → 2단계: ×1.4 → 3단계: 용량 ×1.3
→ 4단계: 스킬 제거 → 5단계: max_tasks 제거 → 6단계: 모든 제약 제거
```

### 3가지 시나리오 (`control/multi_scenario.py`)

| 엔드포인트 | 전략 | 특징 |
|-----------|------|------|
| `/optimize/basic` | 1-Pass | 빠른 결과 |
| `/optimize` | 2-Pass + 재시도 | 균형 |
| `/optimize/premium` | BASIC+STANDARD+PREMIUM 병렬 → 최고 점수 선택 | 최고 품질 |

VROOM 파라미터 세부 조정은 `control/vroom_config.py`.
전체 흐름 조율은 `control/controller.py`.

---

## 4층. VROOM 실행 — "실제로 돌리는 부분"

`optimization/vroom_executor.py` — 딱 하나의 일만 한다:

```bash
vroom -r osrm -a car:localhost -p car:5000 -t 4 -x 5 -g -i -
```

- stdin으로 JSON 넣고, stdout으로 결과 받음 (subprocess)
- `-g`: geometry(경로 좌표) 요청
- `-t 4`: 4스레드 / `-x 5`: 탐색 깊이 5

**래퍼의 나머지 코드가 전부 "이 한 줄을 효과적으로 호출하기 위한" 준비와 후속 작업이다.**

---

## 5층. 후처리 — "VROOM 결과에 가치를 더하기"

VROOM 응답은 `routes`와 `unassigned`뿐이다. 래퍼가 분석을 붙인다.

### ① 미배정 사유 역추적 (`postprocessing/constraint_checker.py`)

VROOM은 "이 작업 못 넣었다"만 알려주고 **왜 못 넣었는지는 안 알려준다.**

```
unassigned job 5 → 왜?
  ├─ skills 확인: 차량에 skill 10000(VIP) 없음 ✗
  ├─ capacity 확인: OK
  ├─ time_window 확인: OK
  └─ 결론: reasons = ["VIP 스킬 보유 차량 없음"]
```

### ② 품질 점수 (`postprocessing/analyzer.py`)

0~100점:
- 배정률 40% + 경로 균형도 30% + 시간창 활용 20% + 비용 효율 10%
- 점수 낮으면 개선 제안 생성 ("차량 추가 권장", "시간창 완화 필요")

### ③ 통계 (`postprocessing/statistics.py`)

- 차량별: 작업수, 거리, 시간, 용량 사용률
- 비용: 총 거리(km), 총 시간(h), 서비스/대기 시간
- 효율: 작업당 거리, 이동 시간 비율

---

## 6층. HGLIS — "완전히 다른 포맷의 통번역"

HGLIS(가전배송) 도메인은 VROOM과 입력 포맷이 완전히 다르다.
`hglis/` 모듈이 HGLIS 비즈니스 언어 → VROOM 수학 언어로 1:1 통번역한다.

### 포맷 변환 대응표

| HGLIS 입력 | → | VROOM 입력 |
|-----------|---|-----------|
| `skill_grade: "A"` | → | `vehicle.skills: [1,2,3]` (기능도 A = C+B+A 가능) |
| `product.required_grade: "B"` | → | `job.skills: [2]` (B 이상만 배정) |
| `scheduling.preferred_time_slot: "오전1"` | → | `job.time_windows: [[unix_start, unix_end]]` |
| `capacity_cbm: 15.0` | → | `vehicle.capacity: [1500, 0, 0]` (×100 정수화) |
| `region_code: "Y1"` | → | 권역 분할 후 별도 VROOM 호출 |
| `crew.size: 2` | → | `job.skills: [크루2인 전용 skill]` |
| `is_new_product: true` | → | `job.skills: [신제품 skill]` (C7 제약) |

### 처리 흐름 (`hglis/dispatcher.py`가 오케스트레이션)

```
HGLIS JSON
  │
  ▼ hglis/validator.py
① 검증          — HGLIS 필수 필드, 권역코드, 좌표 범위
  │
  ▼ hglis/time_converter.py
② 시간 변환     — "오전1" → Unix timestamp 범위
  │
  ▼ hglis/joint_dispatch.py
③ 합배차 처리   — 2인 배송 pickup↔delivery 연계 전처리
  │
  ▼ hglis/skill_encoder.py
④ 스킬 인코딩  — 기능도/신제품/소파/반납 → VROOM skill 번호
  │
  ▼ hglis/region_splitter.py
⑤ 권역 분할    — Y1/Y2/Y3 등 권역별로 분리
  │
  ▼ hglis/vroom_assembler.py
⑥ VROOM 조립  — HGLIS Job/Vehicle → VROOM Job/Vehicle 완성
  │
  ▼ [VROOM 실행 — 권역별 병렬]
⑦ 최적화       — 권역별 독립 실행 후 결과 병합
  │
  ▼ hglis/fee_validator.py
⑧ 설치비 검증  — C2: 기사 일일 수익 하한 검증
  │
  ▼ hglis/monthly_cap.py
⑨ 월 상한 검증 — C6: 서비스등급별 월 수익 상한 (S:1200만/A:1100만/B:900만/C:700만)
```

---

## 최종 응답 — VROOM이 준 것 vs 래퍼가 추가한 것

```jsonc
{
  // ── VROOM이 준 것 ──
  "routes": [...],            // 차량별 경로 (steps, geometry 포함)
  "summary": {...},           // 비용/거리/시간 합계
  "unassigned": [...],        // 미배정 목록 (VROOM은 사유 없음)

  // ── 래퍼가 추가한 것 ──
  "unassigned[].reasons": [...],    // ← 미배정 사유 역추적
  "analysis": {
    "quality_score": 85.5,          // ← 0~100점 품질 점수
    "suggestions": [...]            // ← 개선 제안
  },
  "statistics": {
    "vehicle_utilization": [...],   // ← 차량별 효율
    "cost_breakdown": {...},        // ← 비용 분석
    "time_analysis": {...},         // ← 시간 분석
    "efficiency_metrics": {...}     // ← 효율 지표
  },
  "_metadata": {
    "processing_time_ms": 2500,     // ← 처리 시간
    "from_cache": false             // ← Redis 캐시 히트 여부
  }
}
```

---

## 엔드포인트별 파이프라인 요약

| 엔드포인트 | 전처리 | 최적화 | 후처리 | 비고 |
|-----------|--------|--------|--------|------|
| `/distribute` | Validator만 | 1-Pass | 미배정 분석 | 인증 불필요 |
| `/optimize` | 풀 파이프라인 (OSRM) | 2-Pass + 재시도 | 전체 분석 | STANDARD |
| `/optimize/basic` | 풀 파이프라인 (OSRM) | 1-Pass | 전체 분석 | 빠른 결과 |
| `/optimize/premium` | 풀 파이프라인 (OSRM) | 멀티 시나리오 | 전체 분석 | 최고 품질 |
| `/dispatch` | HGLIS 전용 7단계 | 권역별 병렬 2-Pass | C2/C6 검증 | 가전배송 |
| `/valhalla/distribute` | Validator + Valhalla 매트릭스 | 1-Pass | 미배정 분석 | OSRM 대신 Valhalla |
| `/valhalla/optimize` | 풀 파이프라인 (Valhalla) | 2-Pass + 재시도 | 전체 분석 | ETA 정확도 향상 |

---

## 한 장 정리

```
┌─────────────────────────────────────────────────────────┐
│                    래퍼의 역할 요약                        │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  [전처리]                                                │
│  검증 → 정규화 → 비즈니스 규칙 번역 → 도달불가 제거          │
│  → OSRM/Valhalla 매트릭스 사전 계산                       │
│                                                         │
│  [실행]                                                  │
│  VROOM 바이너리 호출 (stdin/stdout subprocess)            │
│                                                         │
│  [후처리]                                                │
│  미배정 사유 역추적 → 품질 점수 → 통계 생성 → 캐싱          │
│                                                         │
│  [HGLIS 통번역]                                          │
│  가전배송 도메인 언어 ↔ VROOM 수학 언어 1:1 변환           │
│                                                         │
│  VROOM은 수학만. 나머지 전부가 래퍼.                       │
└─────────────────────────────────────────────────────────┘
```

---

## 확장 풀버전 문서 안내

| 문서 | 내용 |
|------|------|
| [`docs/TECHNICAL-ARCHITECTURE.md`](docs/TECHNICAL-ARCHITECTURE.md) | **이 문서의 확장 풀버전** — 알고리즘 상세, VROOM 내부 구조, OSRM/Valhalla 참조, 성능 최적화 |
| [`docs/WRAPPER_PROCESSING_LOGIC_v1.md`](docs/WRAPPER_PROCESSING_LOGIC_v1.md) | HGLIS 비즈니스 제약(C1~C8) 처리 로직 상세 |
| [`API-DOCUMENTATION.md`](API-DOCUMENTATION.md) | 모든 엔드포인트 입출력 스펙 + 예시 |
| [`docs/HGLIS_배차엔진_통합명세서_v8.3.md`](docs/HGLIS_배차엔진_통합명세서_v8.3.md) | HGLIS 도메인 명세 원문 |
