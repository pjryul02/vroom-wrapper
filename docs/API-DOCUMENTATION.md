# VROOM Wrapper v3.0 API 문서

VRP(Vehicle Routing Problem) 최적화 플랫폼 - Python FastAPI 기반 VROOM C++ 바이너리 래퍼

---

## 목차

1. [빠른 시작 — 이럴 땐 이렇게](#빠른-시작--이럴-땐-이렇게)
   - [시나리오 A: HGLIS 배차 시뮬레이터 / 실 시스템](#시나리오-a-hglis-배차-시뮬레이터--실-시스템)
   - [시나리오 B: Route Playground 연동](#시나리오-b-route-playground-연동)
   - [시나리오 C: 빠른 테스트 / 프로토타이핑](#시나리오-c-빠른-테스트--프로토타이핑)
   - [시나리오 D: GPS 데이터 후처리](#시나리오-d-gps-데이터-후처리)
   - [엔드포인트 선택 기준 한눈에 보기](#엔드포인트-선택-기준-한눈에-보기)
2. [기본 정보](#기본-정보)
   - [Base URL](#base-url)
   - [인증](#인증)
   - [요청률 제한](#요청률-제한)
3. [아키텍처 및 처리 파이프라인](#아키텍처-및-처리-파이프라인)
4. [엔드포인트 목록](#엔드포인트-목록)
5. [엔드포인트 상세](#엔드포인트-상세)
   - [GET / - 루트](#1-get----루트)
   - [GET /health - 헬스 체크](#2-get-health---헬스-체크)
   - [POST /distribute - VROOM 호환](#3-post-distribute---vroom-호환)
   - [POST /optimize - 표준 최적화](#4-post-optimize---표준-최적화)
   - [POST /optimize/basic - 기본 최적화](#5-post-optimizebasic---기본-최적화)
   - [POST /optimize/premium - 프리미엄 최적화](#6-post-optimizepremium---프리미엄-최적화)
   - [POST /dispatch - HGLIS 배차](#7-post-dispatch---hglis-배차)
   - [GET /jobs/{job_id} - 비동기 작업 조회](#8-get-jobsjob_id---비동기-작업-조회)
   - [POST /matrix/build - 청크 매트릭스](#9-post-matrixbuild---청크-매트릭스)
   - [POST /map-matching/match - GPS 궤적 매칭](#10-post-map-matchingmatch---gps-궤적-매칭)
   - [GET /map-matching/health - 맵 매칭 헬스](#11-get-map-matchinghealth---맵-매칭-헬스)
   - [POST /map-matching/validate - 궤적 검증](#12-post-map-matchingvalidate---궤적-검증)
   - [DELETE /cache/clear - 캐시 초기화](#13-delete-cacheclear---캐시-초기화)
   - [POST /valhalla/distribute - Valhalla 배차](#14-post-valhalladistribute---valhalla-배차)
   - [POST /valhalla/optimize - Valhalla 표준 최적화](#15-post-valhallaoptimize---valhalla-표준-최적화)
   - [POST /valhalla/optimize/basic - Valhalla 기본 최적화](#16-post-valhallaoptimizebasic---valhalla-기본-최적화)
   - [POST /valhalla/optimize/premium - Valhalla 프리미엄 최적화](#17-post-valhallaoptimizepremium---valhalla-프리미엄-최적화)
6. [요청 형식](#요청-형식)
   - [VROOM 표준 (Vehicles, Jobs, Shipments)](#vroom-표준-vehicles-jobs-shipments)
   - [HGLIS 형식 (HglisVehicle, HglisJob)](#hglis-형식-hglisvehicle-hglisjob)
7. [응답 형식](#응답-형식)
   - [미배정 사유 유형](#미배정-사유-유형)
   - [분석 및 통계](#분석-및-통계)
8. [에러 코드](#에러-코드)
9. [환경 변수](#환경-변수)
10. [Docker 배포](#docker-배포)
11. [버전 이력](#버전-이력)

---

## 빠른 시작 — 이럴 땐 이렇게

API 레퍼런스보다 먼저 읽어야 할 섹션. **내가 어떤 상황인지**에 맞는 패턴을 바로 골라서 쓴다.

---

### 시나리오 A: HGLIS 배차 시뮬레이터 / 실 시스템

> **"가전 배송 배차 결과가 필요하다. 기사, 오더, 제품, 스케줄 정보를 가지고 있다."**

**쓸 엔드포인트: `POST /dispatch`**

HGLIS 비즈니스 도메인 그대로 넣으면 된다. VROOM 포맷으로 변환하거나 스킬 인코딩을 직접 할 필요 없다. 래퍼가 다음을 자동으로 처리한다:

- 기능도(C1) / 용량(C3) / 배송건수(C4) / 시간대(C5) 제약 → VROOM skills/capacity로 인코딩
- OSRM 매트릭스 계산 (1회)
- 도달 불가능 오더 사전 필터링
- 2-Pass 최적화 (배정 → 경로 순서)
- 설치비 하한(C2) / 월수익 상한(C6) 사후 검증
- 미배정 사유 분류 (어떤 제약 때문에 못 받았는지 명시)

**기본 흐름 (동기 모드, 건수 적을 때):**

```bash
POST /dispatch
X-API-Key: demo-key-12345

{
  "meta": {
    "date": "2026-02-28",
    "region_mode": "strict"    # strict(기본) | flexible | ignore
  },
  "jobs": [
    {
      "id": 1,
      "order_id": "ORD-001",
      "location": [126.97, 37.55],
      "region_code": "Y1",
      "products": [
        {
          "model_code": "TV-65",
          "cbm": 1.5,
          "fee": 50000,
          "required_grade": "C",
          "is_new_product": false,
          "is_sofa": false
        }
      ],
      "scheduling": {
        "preferred_time_slot": "오전1",   # 오전1 | 오후1 | 오후2 | 오후3 | 하루종일
        "service_minutes": 30
      }
    }
  ],
  "vehicles": [
    {
      "id": 1,
      "driver_id": "DRV-001",
      "driver_name": "홍길동",
      "grade": "A",              # S | A | B | C (기능도, C1 제약 기준)
      "service_grade": "A",
      "capacity_cbm": 10.0,
      "location": {
        "start": [127.05, 37.50],  # 물류센터(상차지) 좌표
        "end": [127.05, 37.50],    # 기사 자택 좌표
        "home": [127.05, 37.50],
        "center": [127.05, 37.50]
      },
      "region_code": "Y1",
      "center_code": "용인",
      "crew": { "size": 1, "type": "1인팀", "is_filler": false, "can_joint_dispatch": true },
      "exclusions": { "excluded_skus": [], "avoid_models": [] },
      "fee_status": { "monthly_accumulated": 0, "daily_target": 250000 }
    }
  ],
  "options": {
    "max_tasks_per_driver": 12,
    "geometry": false
  }
}
```

**선택적 vehicle 필드 (필요할 때만 추가):**

```json
"new_product_restricted": true,           // C7: 신제품 배정 금지
"avoid_models": [{ "model": "TV-X99" }], // C8: 특정 모델 미결 이력
"fee_status": { "monthly_accumulated": 6500000 } // C6: 당월 누적 수익
```

**대량 배차(오더 50건+)는 비동기 모드 필수:**

```bash
# 1단계: 비동기로 요청 → job_id 즉시 반환
POST /dispatch?async=true
→ { "job_id": "abc-123", "status": "queued", "poll_url": "/jobs/abc-123" }

# 2단계: 진행률 폴링 (0%~100%)
GET /jobs/abc-123
→ { "status": "running", "progress": 60, "stage": "optimizing" }

# 3단계: 완료 확인
GET /jobs/abc-123
→ { "status": "completed", "result": { ... 배차 결과 ... } }
```

**응답에서 확인할 것:**

```json
{
  "status": "success",
  "results": [
    {
      "order_id": "ORD-001",
      "model_name": "냉장고 870L",
      "driver_id": "DRV-001",
      "delivery_sequence": 1,
      "estimated_arrival": "10:30",
      "install_fee": 50000
    }
  ],
  "unassigned": [
    {
      "order_id": "ORD-002",
      "description": "ORD-002",
      "reasons": [
        {
          "type": "capacity",
          "description": "CBM 용량 초과 — 배정 가능한 기사 없음"
        }
      ]
    }
  ],
  "driver_summary": [...],
  "statistics": {
    "total_orders": 10,
    "assigned_orders": 8,
    "assignment_rate": 80.0
  },
  "warnings": [...]
}
```

`unassigned[].reasons[]` 배열에 미배정 사유가 담긴다. `type`은 VROOM 제약 유형, `description`은 한국어 사유 설명.

---

### 시나리오 B: Route Playground 연동

> **"플레이그라운드 UI에서 여러 엔진을 비교 테스트하고 싶다."**

플레이그라운드 백엔드(`POST /solve/{server}`)가 래퍼로 프록시한다. 직접 래퍼를 호출할 필요 없고, 플레이그라운드에서 서버를 선택하면 된다.

**VROOM + OSRM 계열** (정적 거리, 빠른 응답):

| 플레이그라운드 서버 선택 | 실제 호출 | 특징 |
|---|---|---|
| `vroom-distribute` | `POST /distribute` | 가장 빠름. 인증 불필요. 비즈니스 룰 없음 |
| `vroom-optimize-basic` | `POST /optimize/basic` | 1-Pass. 빠른 결과 |
| `vroom-optimize` | `POST /optimize` | 2-Pass 최적화. 도달불가 필터 포함 |
| `vroom-optimize-premium` | `POST /optimize/premium` | 3-시나리오 병렬 실행 → 최적해 선택 |

**VROOM + Valhalla 계열** (시간대별 ETA 보정 포함):

| 플레이그라운드 서버 선택 | 실제 호출 | 특징 |
|---|---|---|
| `valhalla-distribute` | `POST /valhalla/distribute` | 1-Pass. 인증 불필요. Valhalla 라우팅 |
| `valhalla-optimize-basic` | `POST /valhalla/optimize/basic` | 1-Pass + ETA 보정 |
| `valhalla-optimize` | `POST /valhalla/optimize` | 2-Pass + ETA 보정 |
| `valhalla-optimize-premium` | `POST /valhalla/optimize/premium` | 3-시나리오 병렬 + ETA 보정 |

**OR-Tools 계열** (플레이그라운드 백엔드 내장):

| 플레이그라운드 서버 선택 | 실제 호출 | 특징 |
|---|---|---|
| `ortools-local` | 내장 OR-Tools | 직선거리 (OSRM 미사용). 초고속 |
| `ortools-advanced` | 내장 OR-Tools + OSRM | OSRM 거리행렬 기반. 정확한 거리 |

**HGLIS 계열**:

| 플레이그라운드 서버 선택 | 실제 호출 | 특징 |
|---|---|---|
| `hglis-dispatch` | `POST /dispatch` | 가전배차 C1~C8 룰. 권역 2-Pass |

래퍼를 직접 호출해야 하는 경우(플레이그라운드 외부):
- HGLIS 배차 → 시나리오 A
- 순수 VROOM 포맷 테스트 → `POST /distribute` (인증 불필요)

---

### 시나리오 C: 빠른 테스트 / 프로토타이핑

> **"일단 돌아가는지 보고 싶다. 복잡한 제약 없이 기본 VRP만."**

**`POST /distribute` 부터 시작해라.** API Key 없어도 되고, VROOM 표준 JSON 그대로 쓴다.

```bash
POST /distribute
Content-Type: application/json

{
  "vehicles": [
    {
      "id": 1,
      "start": [127.05, 37.50],
      "end": [127.05, 37.50],
      "capacity": [100]
    }
  ],
  "jobs": [
    { "id": 1, "location": [126.97, 37.55], "delivery": [1] },
    { "id": 2, "location": [126.98, 37.56], "delivery": [1] }
  ]
}
```

결과 보고 만족스러우면 `/optimize`로 올려라. 비즈니스 제약(등급/권역/설치비) 필요하면 `/dispatch`로.

**`/optimize` vs `/distribute` 차이:**

| | `/distribute` | `/optimize` |
|---|---|---|
| API Key | 불필요 | 필요 |
| 처리 | VROOM 바이너리 직접 호출 | 전처리 + 2-Pass + 분석 |
| 도달불가 필터 | 없음 | 있음 |
| 미배정 사유 | 없음 | 있음 |
| 속도 | 빠름 | 느림 (더 정확) |

---

### 시나리오 D: GPS 데이터 후처리

> **"기사 GPS 궤적을 도로에 맞추고 싶다. 실제 주행 경로 복원이 필요하다."**

**`POST /map-matching/match` → (선택) `POST /matrix/build` 조합으로 쓴다.**

```bash
# 1단계: GPS 궤적 → 도로 스냅
POST /map-matching/match
X-API-Key: demo-key-12345

{
  "trajectory": [
    { "longitude": 127.001, "latitude": 37.501, "timestamp": 1700000000 },
    { "longitude": 127.003, "latitude": 37.503, "timestamp": 1700000060 },
    { "longitude": 127.006, "latitude": 37.506, "timestamp": 1700000120 }
  ]
}
→ 도로에 스냅된 좌표 반환 + confidence score

# 2단계 (선택): 스냅된 좌표들로 매트릭스 계산
POST /matrix/build
X-API-Key: demo-key-12345

{
  "locations": [
    [127.001, 37.501],
    [127.003, 37.503],
    [127.006, 37.506]
  ]
}
→ durations / distances 매트릭스 반환
```

매칭 품질 먼저 검증하려면 `/map-matching/validate`로 점수만 뽑아볼 수 있다.

---

### 엔드포인트 선택 기준 한눈에 보기

```
나는 HGLIS 가전 배송 배차가 필요하다
  └→ POST /dispatch

나는 일반 VRP 최적화가 필요하다
  ├─ VROOM + OSRM (정적 거리, 빠름)
  │   ├─ 빠른 테스트 / 인증 없이 → POST /distribute
  │   ├─ 비즈니스 로직 + 분석 필요 → POST /optimize
  │   ├─ 속도 우선 (1-Pass) → POST /optimize/basic
  │   └─ 정확도 우선 (3-시나리오 병렬) → POST /optimize/premium
  │
  └─ VROOM + Valhalla (시간대별 ETA 보정)
      ├─ 빠른 테스트 / 인증 없이 → POST /valhalla/distribute
      ├─ 표준 + ETA 보정 → POST /valhalla/optimize
      ├─ 속도 우선 (1-Pass) → POST /valhalla/optimize/basic
      └─ 정확도 우선 (3-시나리오 + ETA) → POST /valhalla/optimize/premium

나는 GPS 궤적을 도로에 맞춰야 한다
  └→ POST /map-matching/match

나는 좌표 간 거리/시간 매트릭스만 뽑고 싶다
  └→ POST /matrix/build

나는 비동기로 결과를 받아야 한다 (대용량)
  └→ /dispatch?async=true 또는 /optimize?async=true 후 GET /jobs/{id} 폴링
```

---

## 기본 정보

### Base URL

```
http://localhost:8000        # 로컬 개발
http://YOUR_IP:8000          # 외부 접근
https://yourdomain.com       # 프로덕션
```

### Content-Type

```
Content-Type: application/json
```

### 인증

API Key 헤더 인증 방식을 사용한다.

| 헤더 | 값 |
|------|------|
| `X-API-Key` | 발급받은 API Key |

데모 키: `demo-key-12345`

```bash
# API Key 헤더 포함 요청
curl -H "X-API-Key: demo-key-12345" http://localhost:8000/optimize
```

**인증 요구 사항 요약**:

| 엔드포인트 | API Key 필요 |
|------------|:------------:|
| `GET /` | 불필요 |
| `GET /health` | 불필요 |
| `POST /distribute` | 불필요 |
| `POST /optimize` | 필요 |
| `POST /optimize/basic` | 필요 |
| `POST /optimize/premium` | 필요 |
| `POST /dispatch` | 필요 |
| `GET /jobs/{job_id}` | 불필요 |
| `POST /matrix/build` | 필요 |
| `POST /map-matching/match` | 필요 |
| `GET /map-matching/health` | 불필요 |
| `POST /map-matching/validate` | 필요 |
| `DELETE /cache/clear` | 필요 |
| `POST /valhalla/distribute` | 불필요 |
| `POST /valhalla/optimize` | 필요 |
| `POST /valhalla/optimize/basic` | 필요 |
| `POST /valhalla/optimize/premium` | 필요 |

### 요청률 제한

API Key 단위로 요청률 제한(Rate Limiting)이 적용된다.

| 구분 | 제한 | 기간 |
|------|------|------|
| 기본 엔드포인트 | 100 요청 | 3600초 (1시간) |
| 프리미엄 엔드포인트 | 50 요청 | 3600초 (1시간) |

제한 초과 시 HTTP `429 Too Many Requests` 응답이 반환된다.

---

## 아키텍처 및 처리 파이프라인

### 서비스 구성

```
┌─────────────────┐     ┌──────────┐     ┌─────────┐
│  Wrapper (8000) │────▶│ OSRM     │     │ Redis   │
│  Python/FastAPI │     │ (5000)   │     │ (6379)  │
│  + VROOM Binary │     └──────────┘     └─────────┘
│                 │────▶┌──────────┐
│                 │     │ Valhalla │  ← /valhalla/* 및 HGLIS ETA 보정
└─────────────────┘     │ (8002)   │
                        └──────────┘
```

- **Wrapper**: FastAPI + VROOM C++ 바이너리 (subprocess 직접 호출)
- **OSRM**: MLD 알고리즘 기반 도로 라우팅 엔진 (정적 거리행렬)
- **Valhalla**: 시간대 의존 라우팅 엔진 (ETA 보정, 한국 전체 데이터)
- **Redis**: 캐싱 (선택, 미연결 시 인메모리 폴백)

### 최적화 처리 파이프라인

`/optimize` 및 `/dispatch` 엔드포인트는 다음 파이프라인을 거친다:

```
① 매트릭스 사전 계산 (OSRM 1회 호출)
   좌표 → OSRM Table API → durations/distances 매트릭스

② 도달 불가능 필터링
   매트릭스 기반으로 어떤 차량도 도달할 수 없는 작업 사전 제거

③ 2-Pass 최적화
   Pass 1: 초기 배정 (어떤 차량에 어떤 작업 → threads=16)
   Pass 2: 경로별 순서 최적화 (서브매트릭스 → threads=4, 병렬)

④ 미배정 자동 재시도
   제약 완화 후 재시도 (unreachable 제외)

⑤ 후처리
   분석, 통계, 캐싱
```

**핵심**: 매트릭스를 한 번만 계산하여 모든 단계에서 재활용. OSRM 반복 호출 없음.

---

## 엔드포인트 목록

| # | 메서드 | 경로 | 설명 | 인증 |
|---|--------|------|------|:----:|
| 1 | GET | `/` | 서비스 정보 | 불필요 |
| 2 | GET | `/health` | 헬스 체크 | 불필요 |
| 3 | POST | `/distribute` | VROOM 호환 최적화 | 불필요 |
| 4 | POST | `/optimize` | 표준 최적화 (전체 파이프라인) | 필요 |
| 5 | POST | `/optimize/basic` | 기본 최적화 (빠른 결과) | 필요 |
| 6 | POST | `/optimize/premium` | 프리미엄 최적화 (멀티 시나리오) | 필요 |
| 7 | POST | `/dispatch` | HGLIS 배차 (동기/비동기) | 필요 |
| 8 | GET | `/jobs/{job_id}` | 비동기 작업 진행률/결과 조회 | 불필요 |
| 9 | POST | `/matrix/build` | OSRM 청크 매트릭스 생성 | 필요 |
| 10 | POST | `/map-matching/match` | GPS 궤적 맵 매칭 | 필요 |
| 11 | GET | `/map-matching/health` | 맵 매칭 서비스 헬스 체크 | 불필요 |
| 12 | POST | `/map-matching/validate` | 궤적 품질 검증 | 필요 |
| 13 | DELETE | `/cache/clear` | 캐시 전체 초기화 | 필요 |
| 14 | POST | `/valhalla/distribute` | Valhalla 1-Pass 배차 (VROOM 호환, 인증 불필요) | 불필요 |
| 15 | POST | `/valhalla/optimize/basic` | Valhalla 1-Pass + ETA 보정 | 필요 |
| 16 | POST | `/valhalla/optimize` | Valhalla 2-Pass + ETA 보정 | 필요 |
| 17 | POST | `/valhalla/optimize/premium` | Valhalla 3-시나리오 병렬 + ETA 보정 (최고 품질) | 필요 |

---

## 엔드포인트 상세

---

### 1. GET / -- 루트

서비스 정보, 버전, 사용 가능한 엔드포인트 목록을 반환한다.

**인증**: 불필요

**요청**:

```bash
curl http://localhost:8000/
```

**응답 예시**:

```json
{
  "service": "VROOM Wrapper v3.0 - Synthesis Edition",
  "version": "3.0.0",
  "architecture": "Roouty Engine (Go) + Python Wrapper synthesis",
  "endpoints": {
    "distribute": "POST /distribute (VROOM+OSRM, 인증 불필요)",
    "optimize_basic": "POST /optimize/basic (VROOM+OSRM 1-Pass, 인증 필요)",
    "optimize": "POST /optimize (VROOM+OSRM 2-Pass, 인증 필요)",
    "optimize_premium": "POST /optimize/premium (VROOM+OSRM 3-시나리오, 인증 필요)",
    "dispatch": "POST /dispatch (HGLIS 가전배차 C1~C8, 인증 필요)",
    "valhalla_distribute": "POST /valhalla/distribute (VROOM+Valhalla, 인증 불필요)",
    "valhalla_optimize_basic": "POST /valhalla/optimize/basic (Valhalla 1-Pass+ETA, 인증 필요)",
    "valhalla_optimize": "POST /valhalla/optimize (Valhalla 2-Pass+ETA, 인증 필요)",
    "valhalla_optimize_premium": "POST /valhalla/optimize/premium (Valhalla 3-시나리오+ETA, 인증 필요)",
    "jobs": "GET /jobs/{job_id} (비동기 작업 조회)",
    "matrix": "POST /matrix/build (OSRM 거리/시간 매트릭스)",
    "map_matching": "POST /map-matching/match (GPS 궤적 맵매칭, 인증 필요)",
    "cache_clear": "DELETE /cache/clear (캐시 초기화, 인증 필요)",
    "swagger_ui": "GET /docs (Swagger UI)"
  },
  "authentication": "X-API-Key 헤더 (distribute/valhalla-distribute 제외 필요)",
  "demo_api_key": "demo-key-12345"
}
```

---

### 2. GET /health -- 헬스 체크

서비스 구성 요소의 상태를 반환한다.

**인증**: 불필요

**요청**:

```bash
curl http://localhost:8000/health
```

**응답 예시**:

```json
{
  "status": "healthy",
  "version": "3.0.0",
  "engine": "direct",
  "components": {
    "vroom_binary": "healthy",
    "two_pass": "enabled",
    "unreachable_filter": "enabled",
    "cache": "redis",
    "map_matching": "healthy"
  }
}
```

**components 필드**:

| 필드 | 가능한 값 | 설명 |
|------|-----------|------|
| `vroom_binary` | `healthy` / `unhealthy` / `http_fallback` | VROOM 바이너리 상태 |
| `two_pass` | `enabled` / `disabled` | 2-Pass 최적화 활성 여부 |
| `unreachable_filter` | `enabled` / `disabled` | 도달 불가 필터 활성 여부 |
| `cache` | `redis` / `memory` | 캐시 백엔드 |
| `map_matching` | `healthy` / `disabled` | 맵 매칭 서비스 상태 |

**상태 코드**:

| 코드 | 설명 |
|------|------|
| `200 OK` | 핵심 서비스 정상 |
| `503 Service Unavailable` | 핵심 컴포넌트 이상 |

---

### 3. POST /distribute -- VROOM 호환

VROOM 표준 JSON 형식을 그대로 사용하는 호환 엔드포인트이다. API Key 없이 사용할 수 있다.
VROOM C++ 바이너리를 직접 호출하며, OSRM을 통해 항상 geometry를 포함한 정확한 거리 정보를 얻는다.

**인증**: 불필요

**처리 방식**: VROOM 바이너리 1회 직접 호출 (2-Pass 파이프라인 미적용)

**요청 형식**: VROOM 표준 JSON (vehicles, jobs, shipments, options)

**요청**:

```bash
curl -X POST http://localhost:8000/distribute \
  -H "Content-Type: application/json" \
  -d '{
    "vehicles": [
      {
        "id": 1,
        "start": [126.9780, 37.5665],
        "end": [126.9780, 37.5665],
        "capacity": [100],
        "skills": [1, 2],
        "time_window": [28800, 64800]
      }
    ],
    "jobs": [
      {
        "id": 101,
        "location": [127.0276, 37.4979],
        "service": 300,
        "delivery": [20],
        "skills": [1],
        "time_windows": [[32400, 36000]]
      },
      {
        "id": 102,
        "location": [127.0594, 37.5140],
        "service": 600,
        "delivery": [30],
        "skills": [3],
        "time_windows": [[43200, 50400]]
      }
    ]
  }'
```

**응답 예시**:

```json
{
  "code": 0,
  "summary": {
    "cost": 1234,
    "routes": 1,
    "unassigned": 1,
    "service": 300,
    "duration": 2400,
    "waiting_time": 0,
    "distance": 12500,
    "violations": []
  },
  "routes": [
    {
      "vehicle": 1,
      "cost": 1234,
      "service": 300,
      "duration": 2400,
      "distance": 12500,
      "steps": [
        {
          "type": "start",
          "location": [126.9780, 37.5665],
          "arrival": 28800,
          "duration": 0
        },
        {
          "type": "job",
          "id": 101,
          "location": [127.0276, 37.4979],
          "arrival": 32400,
          "duration": 3600,
          "service": 300,
          "load": [20]
        },
        {
          "type": "end",
          "location": [126.9780, 37.5665],
          "arrival": 35400,
          "duration": 6600
        }
      ],
      "violations": [],
      "geometry": "encoded_polyline_string..."
    }
  ],
  "unassigned": [
    {
      "id": 102,
      "location": [127.0594, 37.5140],
      "type": "job",
      "reasons": [
        {
          "type": "skills",
          "description": "No vehicle has required skills",
          "details": {
            "required_skills": [3],
            "available_vehicle_skills": [[1, 2]]
          }
        }
      ]
    }
  ],
  "_wrapper": {
    "version": "3.0.0",
    "engine": "direct",
    "processing_time_ms": 450
  }
}
```

**Wrapper 추가 필드**:
- `unassigned[].reasons`: 미배정 사유 분석 결과
- `_wrapper`: 래퍼 메타데이터

**geometry 제어**: 요청 시 `"options": {"g": true}` 포함하면 응답에 geometry 필드가 유지된다. 기본적으로 래퍼가 내부에서 geometry를 요청하되, 클라이언트가 `"g": true`를 명시하지 않으면 응답에서 제거한다.

**상태 코드**:

| 코드 | 설명 |
|------|------|
| `200 OK` | 최적화 성공 |
| `400 Bad Request` | 잘못된 입력 (vehicles/jobs 누락 등) |
| `500 Internal Server Error` | VROOM 바이너리 실행 오류 |

---

### 4. POST /optimize -- 표준 최적화

전체 파이프라인을 실행하는 표준 최적화 엔드포인트이다.

**처리 순서**: 도달 불가 필터링 → 2-Pass 최적화 (10개 이상 작업 시) → 제약 완화 자동 재시도 → 분석 → 통계 → 캐싱

**인증**: 필요 (`X-API-Key` 헤더)

**추가 입력 필드** (VROOM 표준 필드 외):

| 필드 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| `use_cache` | boolean | `true` | 캐시 사용 여부 |
| `business_rules` | object | `null` | 비즈니스 규칙 설정 |
| `business_rules.vip_job_ids` | [int] | `[]` | VIP 작업 ID 목록 |
| `business_rules.urgent_job_ids` | [int] | `[]` | 긴급 작업 ID 목록 |
| `business_rules.enable_vip` | boolean | `true` | VIP 규칙 활성화 |
| `business_rules.enable_urgent` | boolean | `true` | 긴급 규칙 활성화 |

**요청**:

```bash
curl -X POST http://localhost:8000/optimize \
  -H "Content-Type: application/json" \
  -H "X-API-Key: demo-key-12345" \
  -d '{
    "vehicles": [
      {
        "id": 1,
        "start": [126.9780, 37.5665],
        "end": [126.9780, 37.5665],
        "capacity": [100],
        "skills": [1, 2],
        "time_window": [28800, 64800],
        "max_tasks": 10
      },
      {
        "id": 2,
        "start": [127.0594, 37.5140],
        "end": [127.0594, 37.5140],
        "capacity": [200],
        "skills": [2, 3],
        "time_window": [36000, 72000]
      }
    ],
    "jobs": [
      {
        "id": 101,
        "location": [127.0276, 37.4979],
        "service": 300,
        "delivery": [20],
        "skills": [1],
        "priority": 100,
        "time_windows": [[32400, 36000]]
      },
      {
        "id": 102,
        "location": [127.0594, 37.5140],
        "service": 600,
        "delivery": [30],
        "skills": [2],
        "priority": 80,
        "time_windows": [[43200, 50400]]
      },
      {
        "id": 103,
        "location": [126.9910, 37.5512],
        "service": 300,
        "delivery": [15],
        "time_windows": [[50400, 54000]]
      }
    ],
    "use_cache": true,
    "business_rules": {
      "vip_job_ids": [101],
      "enable_vip": true
    }
  }'
```

**응답 예시**:

```json
{
  "code": 0,
  "summary": {
    "cost": 2850,
    "routes": 2,
    "unassigned": 0,
    "service": 1200,
    "duration": 9600,
    "waiting_time": 300,
    "distance": 35200,
    "violations": []
  },
  "routes": [
    {
      "vehicle": 1,
      "cost": 1400,
      "service": 600,
      "duration": 4800,
      "distance": 18500,
      "steps": [
        {"type": "start", "location": [126.9780, 37.5665], "arrival": 28800, "duration": 0},
        {"type": "job", "id": 101, "location": [127.0276, 37.4979], "arrival": 32400, "duration": 3600, "service": 300, "load": [20]},
        {"type": "job", "id": 103, "location": [126.9910, 37.5512], "arrival": 50400, "service": 300, "load": [35]},
        {"type": "end", "location": [126.9780, 37.5665], "arrival": 51900, "duration": 23100}
      ],
      "geometry": "encoded_polyline_string..."
    }
  ],
  "unassigned": [],
  "analysis": {
    "quality_score": 0.92,
    "suggestions": ["차량 1의 대기 시간이 길어 경로 재배치를 고려하세요"],
    "vehicle_utilization": [
      {"vehicle_id": 1, "utilization": 0.85, "tasks": 2},
      {"vehicle_id": 2, "utilization": 0.65, "tasks": 1}
    ]
  },
  "statistics": {
    "distances": {"total": 35200, "per_vehicle": [18500, 16700]},
    "durations": {"total": 9600, "per_vehicle": [4800, 4800]},
    "averages": {"distance_per_task": 11733, "duration_per_task": 3200}
  },
  "_metadata": {
    "version": "3.0",
    "mode": "optimize",
    "pipeline": ["preprocessing", "unreachable_filter", "two_pass", "vroom", "analysis", "statistics"],
    "cache_hit": false,
    "processing_time_ms": 1250
  }
}
```

**상태 코드**:

| 코드 | 설명 |
|------|------|
| `200 OK` | 최적화 성공 |
| `400 Bad Request` | 잘못된 입력 |
| `401 Unauthorized` | API Key 누락 또는 유효하지 않음 |
| `429 Too Many Requests` | 요청률 제한 초과 |
| `500 Internal Server Error` | 내부 오류 |

---

### 5. POST /optimize/basic -- 기본 최적화

빠른 결과를 위한 경량 최적화 엔드포인트이다. 분석(analysis) 및 통계(statistics) 단계를 건너뛰어 응답 속도가 빠르다.

**인증**: 필요 (`X-API-Key` 헤더)

**요청**: `/optimize`와 동일한 입력 형식

```bash
curl -X POST http://localhost:8000/optimize/basic \
  -H "Content-Type: application/json" \
  -H "X-API-Key: demo-key-12345" \
  -d '{
    "vehicles": [
      {"id": 1, "start": [126.9780, 37.5665], "end": [126.9780, 37.5665], "capacity": [100]}
    ],
    "jobs": [
      {"id": 101, "location": [127.0276, 37.4979], "service": 300, "delivery": [20]},
      {"id": 102, "location": [127.0594, 37.5140], "service": 600, "delivery": [30]}
    ]
  }'
```

**응답**: `analysis`, `statistics` 필드 없이 `code`, `summary`, `routes`, `unassigned`, `_metadata`만 포함.

---

### 6. POST /optimize/premium -- 프리미엄 최적화

3가지 탐색 파라미터 시나리오를 병렬 실행하여 최적해를 선택하는 프리미엄 엔드포인트이다. ETA 보정은 없음 (OSRM 정적 거리 기반).

**인증**: 필요 (`X-API-Key` 헤더, 프리미엄 권한)

**요청률 제한**: 50 요청 / 3600초

**요청**: `/optimize`와 동일한 입력 형식

**응답**: `/optimize` 응답에 추가로 `multi_scenario_metadata` 필드가 포함된다:

```json
{
  "multi_scenario_metadata": {
    "selected_scenario": "scenario_2",
    "total_scenarios": 3,
    "comparison": {
      "scenario_1": {"cost": 3200, "unassigned": 0},
      "scenario_2": {"cost": 2750, "unassigned": 0},
      "scenario_3": {"cost": 2900, "unassigned": 1}
    }
  }
}
```

---

### 7. POST /dispatch -- HGLIS 배차

HGLIS(가전 배송 물류) 전용 배차 엔드포인트이다. HGLIS 비즈니스 규칙(C1~C8 제약)을 적용하고, 매트릭스 사전 계산 → 도달 불가능 필터링 → 2-Pass 최적화 전체 파이프라인을 실행한다.

**인증**: 필요 (`X-API-Key` 헤더)

**비동기 모드**: `?async=true` 쿼리 파라미터로 비동기 실행. job_id 즉시 반환 후 `/jobs/{job_id}`로 진행률 조회.

#### 처리 파이프라인

```
HGLIS 입력 → 검증 → 스킬 인코딩 → VROOM 조립
           → OSRM 매트릭스 사전 계산 (1회)    ← Pass 1+2 기반 공간 거리
           → UnreachableFilter
           → 2-Pass 최적화 (Pass1: 배정, Pass2: 경로최적화)
           → 미배정 재시도
           → C2/C6 설치비 검증
           → [Pass 3] Valhalla ETA 보정         ← 현재 비활성화 (enabled=False)
           → 결과 변환
```

> **Pass 3 (Valhalla ETA 보정)**: 코드가 구현되어 있으나 현재 `enabled=False`로 비활성화 상태.
> 활성화 시 OSRM 기반 도착 시각을 Valhalla 시간대 의존 라우팅으로 재계산하여 ETA 정확도를 높인다.
> 파라미터가 아닌 코드 레벨 설정(`dependencies.py`)으로 제어된다.

#### 요청 구조

```json
{
  "meta": {
    "request_id": "REQ-20260301-001",
    "date": "2026-03-01",
    "region_mode": "strict"
  },
  "vehicles": [...],
  "jobs": [...],
  "options": {
    "max_tasks_per_driver": 12,
    "enable_joint_dispatch": false,
    "geometry": true
  }
}
```

**meta 필드**:

| 필드 | 타입 | 필수 | 설명 |
|------|------|:----:|------|
| `request_id` | string | 선택 | 요청 추적 ID |
| `date` | string | 필수 | 배차 기준일 (YYYY-MM-DD) |
| `region_mode` | string | 선택 | `"strict"` (기본) / `"flexible"` / `"ignore"` |

**region_mode**:
- `strict`: 기사-오더 권역코드 정확 일치 (기본)
- `flexible`: 인접 권역 허용
- `ignore`: 권역 무시 (전체 매칭)

**options 필드**:

```json
{
  "constraints": {
    "C1": true, "C2": true, "C3": true, "C4": true,
    "C5": true, "C6": true, "C7": true, "C8": true
  },
  "constraint_config": {
    "C1": {
      "allow_joint_dispatch": true,
      "joint_fee_split": {"primary": 0.6, "secondary": 0.4}
    },
    "C3": {
      "time_window_buffer_minutes": 60,
      "time_slots": {
        "오전1": {"start": "08:00", "end": "12:00"},
        "오후1": {"start": "12:00", "end": "16:00"},
        "오후2": {"start": "16:00", "end": "19:00"},
        "오후3": {"start": "19:00", "end": "24:00"},
        "하루종일": {"start": "08:00", "end": "24:00"}
      }
    },
    "C2": {
      "min_fee_by_grade": {"2인팀": 400000, "S": 280000, "A": 250000, "B": 220000, "C": 180000},
      "weight": 50
    },
    "C6": {
      "monthly_limit_by_grade": {"S": 12000000, "A": 11000000, "B": 9000000, "C": 7000000},
      "warn_threshold_percent": 90,
      "weight": 70
    }
  },
  "engine": {
    "calc_time_limit": 60,
    "exploration_level": 5,
    "balance_mode": "balanced"
  }
}
```

| 필드 | 설명 |
|------|------|
| `constraints.C1~C8` | 각 제약 활성화 토글 (bool). 기본 모두 true |
| `constraint_config.C3.time_slots` | 시간대별 시작/종료 시각 오버라이드 |
| `constraint_config.C2.min_fee_by_grade` | 등급별 최소 설치비 기준 (원) |
| `constraint_config.C6.monthly_limit_by_grade` | 등급별 월 누적 설치비 상한 (원) |
| `engine.calc_time_limit` | VROOM 탐색 시간 제한 (초) |
| `engine.exploration_level` | VROOM 탐색 깊이 (1~5) |
| `engine.balance_mode` | 부하 분산 모드 (`balanced` / `cost`) |

#### HglisVehicle (기사)

```json
{
  "id": 10000,
  "driver_id": "L0000022",
  "driver_name": "이유승",
  "driver_phone": "010****5460",
  "grade": "S",
  "service_grade": "B",
  "cs_grade": "S",
  "is_rookie": false,
  "hire_date": "2019-12-27",
  "vehicle_type": "카고",
  "vehicle_number": "85어 1139",
  "vehicle_ton": 1.0,
  "capacity_cbm": 4.0,
  "location": {
    "start": [126.978, 37.5665],
    "end": [126.978, 37.5665],
    "home": [126.978, 37.5665],
    "center": [126.978, 37.5665]
  },
  "region_code": "Y3",
  "sub_region_code": "Y3-2",
  "installer_code": "INST-운창로지텍",
  "center_code": "김포",
  "work_time": {
    "start": "08:00",
    "end": "22:00",
    "breaks": []
  },
  "limits": {
    "max_orders": 12,
    "max_distance_km": 200,
    "max_work_minutes": 600
  },
  "crew": {
    "size": 1,
    "type": "1인팀",
    "is_filler": true,
    "can_joint_dispatch": false
  },
  "exclusions": {
    "excluded_skus": [],
    "avoid_models": []
  },
  "fee_status": {
    "monthly_accumulated": 0,
    "daily_target": 280000,
    "monthly_dispatch_days": 0
  },
  "capabilities": {
    "simple_delivery": false,
    "simple_install": false,
    "built_in_closet": false,
    "all_items": false
  }
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|:----:|------|
| `id` | int | 필수 | 기사 고유 ID |
| `driver_id` | string | 필수 | 기사 식별자 |
| `driver_name` | string | 필수 | 기사명 |
| `grade` | string | 필수 | 기능도 (`S`/`A`/`B`/`C`) — C1 제약 기준 |
| `service_grade` | string | 필수 | 서비스등급 (`S`/`A`/`B`/`C`) |
| `cs_grade` | string | 선택 | CS 등급 |
| `is_rookie` | bool | 선택 | 신입 여부 — C7 신제품 제약 기준 |
| `capacity_cbm` | float | 필수 | 적재 용량 (CBM) — C3 제약 기준 |
| `location` | object | 필수 | 위치 정보 (아래 참고) |
| `region_code` | string | 필수 | 소속 권역코드 — C4 제약 기준 |
| `sub_region_code` | string | 선택 | 세부 권역코드 |
| `center_code` | string | 선택 | 물류센터 코드 (start 위치의 소속 센터) |
| `installer_code` | string | 선택 | 설치업체 코드 |
| `work_time` | object | 선택 | 근무 시간 `{start, end, breaks}` |
| `limits` | object | 선택 | 작업 제한 `{max_orders, max_distance_km, max_work_minutes}` |
| `crew` | object | 필수 | 인원 구성 (아래 참고) |
| `exclusions` | object | 선택 | 배정 제외 조건 `{excluded_skus, avoid_models}` — C7/C8 |
| `fee_status` | object | 선택 | 수익 현황 `{monthly_accumulated, daily_target, monthly_dispatch_days}` — C2/C6 |
| `capabilities` | object | 선택 | 취급 가능 품목 플래그 |

**location 구조**:

| 필드 | 설명 |
|------|------|
| `start` | 출발 좌표 — 물류센터(상차지). `center_code`에 해당하는 좌표 |
| `end` | 복귀 좌표 — 기사 자택. 기준정보에서 매핑 |
| `home` | 자택 좌표 (참고용) |
| `center` | 물류센터 좌표 (참고용) |

> **출발지 = 물류센터**: 기사는 권역별 물류센터(상차지)에서 출발한다. 기사 자택이 아님.
> 좌표는 기준정보(배차 시스템)에서 `center_code`로 매핑되어 주입된다.

**crew 구조**:

| 필드 | 설명 |
|------|------|
| `size` | 팀 인원 수 (1 또는 2) |
| `type` | 팀 유형 (`"1인팀"` / `"2인팀"`) |
| `is_filler` | 충원기사 여부 |
| `can_joint_dispatch` | 합배차 가능 여부 |

**grade 설명**: `S` > `A` > `B` > `C` — S 등급 기사는 모든 등급 제품 설치 가능

**허용 권역코드**: `Y1`, `Y2`, `Y3`, `Y5`, `W1`, `대전`, `대구`, `광주`, `원주`, `부산`, `울산`, `제주`

#### HglisJob (오더)

```json
{
  "id": 0,
  "order_id": "20JB26022200001",
  "order_type": "반품",
  "location": [126.841205, 37.558543],
  "region_code": "Y3",
  "address_type": null,
  "customer": {
    "id": "202107262640",
    "name": "홍길동",
    "phone": "010-1234-5678",
    "address": "서울특별시 강서구 공항대로 301",
    "zip": "10011"
  },
  "products": [
    {
      "model_code": "REF-500",
      "model_name": "냉장고 500L",
      "sku_code": "SKU-001",
      "cbm": 2.5,
      "is_new_product": false,
      "quantity": 1
    }
  ],
  "scheduling": {
    "preferred_time_slot": "오전1",
    "preferred_date": "2026-03-05",
    "service_minutes": 55,
    "setup_minutes": 25
  },
  "constraints": {
    "crew_type": "1인",
    "required_grade": "A",
    "is_filler_required": false
  },
  "priority": {
    "level": 0,
    "is_urgent": false
  },
  "fees": {
    "install_fee": 80000,
    "product_sales_amount": 1500000
  },
  "order_channel": "7J",
  "notes": null,
  "special_instructions": null
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|:----:|------|
| `id` | int | 필수 | 오더 고유 ID |
| `order_id` | string | 필수 | 주문번호 |
| `order_type` | string | 선택 | 주문 유형 (`"배달"` / `"반품"` 등) |
| `location` | [lon, lat] | 필수 | 배송지 좌표 |
| `region_code` | string | 필수 | 권역코드 |
| `customer` | object | 선택 | 고객 정보 `{id, name, phone, address, zip}` |
| `products` | array | 선택 | 제품 목록 (빈 배열 허용) |
| `scheduling` | object | 필수 | 배송 스케줄링 |
| `constraints` | object | 필수 | 배정 제약 조건 |
| `priority` | object | 선택 | 우선순위 |
| `fees` | object | 선택 | 수수료 정보 |
| `order_channel` | string | 선택 | 주문 채널 코드 |

**constraints 필드**:

| 필드 | 타입 | 설명 |
|------|------|------|
| `crew_type` | string | 인원 요구 (`"any"` / `"1인"` / `"2인"`) |
| `required_grade` | string | 필요 기능도 (`S`/`A`/`B`/`C`) — C1 제약 기준 |
| `is_filler_required` | bool | 충원기사 필요 여부 |

> `required_grade`는 과거 `products[].required_grade`에 있었으나, 오더 레벨 `constraints.required_grade`로 이동됨.

**products 필드** (선택):

| 필드 | 타입 | 설명 |
|------|------|------|
| `model_code` | string | 모델코드 |
| `sku_code` | string | SKU 코드 — C7/C8 제약 기준 |
| `cbm` | float | CBM (부피) — C3 용량 제약 기준 |
| `is_new_product` | bool | 신제품 여부 — C7 신입×신제품 제약 기준 |
| `quantity` | int | 수량 (기본: 1) |

**scheduling.preferred_time_slot**:

| 값 | 시간대 (constraint_config.C3으로 오버라이드 가능) |
|----|------|
| `오전1` | 08:00~12:00 |
| `오후1` | 12:00~16:00 |
| `오후2` | 16:00~19:00 |
| `오후3` | 19:00~24:00 |
| `하루종일` | 08:00~24:00 |

#### 동기 모드 요청 (기본)

```bash
curl -X POST http://localhost:8000/dispatch \
  -H "Content-Type: application/json" \
  -H "X-API-Key: demo-key-12345" \
  -d '{
    "meta": {"date": "2026-03-01", "region_mode": "ignore"},
    "vehicles": [
      {
        "id": 1, "driver_id": "DRV001", "driver_name": "김기사",
        "grade": "A", "service_grade": "A", "capacity_cbm": 15.0,
        "location": {"start": [127.027, 37.498], "end": [127.027, 37.498], "home": [127.020, 37.490], "center": [127.027, 37.498]},
        "region_code": "Y1", "center_code": "용인",
        "crew": {"size": 1, "type": "1인팀", "is_filler": false, "can_joint_dispatch": true},
        "work_time": {"start": "08:00", "end": "22:00", "breaks": []},
        "limits": {"max_orders": 8},
        "exclusions": {"excluded_skus": [], "avoid_models": []},
        "fee_status": {"monthly_accumulated": 3500000, "daily_target": 250000}
      },
      {
        "id": 2, "driver_id": "DRV002", "driver_name": "이기사",
        "grade": "B", "service_grade": "B", "capacity_cbm": 12.0,
        "location": {"start": [127.035, 37.505], "end": [127.030, 37.500], "home": [127.030, 37.500], "center": [127.035, 37.505]},
        "region_code": "Y1", "center_code": "용인",
        "crew": {"size": 1, "type": "1인팀", "is_filler": false, "can_joint_dispatch": false},
        "work_time": {"start": "08:00", "end": "22:00", "breaks": []},
        "exclusions": {"excluded_skus": [], "avoid_models": []},
        "fee_status": {"monthly_accumulated": 0, "daily_target": 220000}
      }
    ],
    "jobs": [
      {
        "id": 1, "order_id": "ORD-001", "location": [127.029, 37.500],
        "region_code": "Y1",
        "products": [{"model_code": "REF-500", "sku_code": "SKU-001", "cbm": 2.5, "is_new_product": false}],
        "scheduling": {"preferred_time_slot": "오전1", "preferred_date": "2026-03-01", "service_minutes": 45, "setup_minutes": 15},
        "constraints": {"crew_type": "1인", "required_grade": "A", "is_filler_required": false},
        "fees": {"install_fee": 80000}
      },
      {
        "id": 2, "order_id": "ORD-002", "location": [127.032, 37.502],
        "region_code": "Y1",
        "products": [{"model_code": "TV-55", "sku_code": "SKU-002", "cbm": 1.2, "is_new_product": false}],
        "scheduling": {"preferred_time_slot": "오후1", "preferred_date": "2026-03-01", "service_minutes": 30, "setup_minutes": 10},
        "constraints": {"crew_type": "any", "required_grade": "B", "is_filler_required": false},
        "fees": {"install_fee": 50000}
      }
    ],
    "options": {"constraints": {"C1": true, "C2": true, "C3": true, "C4": true, "C5": true, "C6": true, "C7": true, "C8": true}, "engine": {"calc_time_limit": 30, "exploration_level": 5}}
  }'
```

#### 동기 응답 예시

```json
{
  "status": "success",
  "meta": {
    "request_id": null,
    "date": "2026-03-01",
    "execution_time_ms": 118,
    "engine": "direct",
    "vroom_code": 0,
    "regions_processed": ["ALL"]
  },
  "statistics": {
    "total_orders": 2,
    "assigned_orders": 2,
    "unassigned_orders": 0,
    "assignment_rate": 100.0,
    "joint_dispatch_count": 0,
    "total_vehicles": 2,
    "active_vehicles": 1,
    "total_distance_km": 3.2
  },
  "results": [
    {
      "order_id": "ORD-001",
      "model_name": "냉장고 500L",
      "dispatch_type": "단독",
      "driver_id": "DRV001",
      "driver_name": "김기사",
      "secondary_driver_id": null,
      "secondary_driver_name": null,
      "delivery_sequence": 1,
      "scheduled_arrival": "11:42",
      "install_fee": 80000,
      "geometry": null
    },
    {
      "order_id": "ORD-002",
      "model_name": "세탁기 21kg 외 1건",
      "dispatch_type": "단독",
      "driver_id": "DRV001",
      "driver_name": "김기사",
      "secondary_driver_id": null,
      "secondary_driver_name": null,
      "delivery_sequence": 2,
      "scheduled_arrival": "13:05",
      "install_fee": 50000,
      "geometry": null
    }
  ],
  "driver_summary": [
    {
      "driver_id": "DRV001",
      "driver_name": "김기사",
      "grade": "A",
      "service_grade": "A",
      "assigned_count": 2,
      "total_fee": 130000,
      "distance_km": 3.2,
      "c2_status": "ok",
      "c2_threshold": 0,
      "monthly_after": 130000,
      "c6_status": "ok",
      "c6_cap": 11000000
    },
    {
      "driver_id": "DRV002",
      "driver_name": "이기사",
      "grade": "B",
      "service_grade": "B",
      "assigned_count": 0,
      "total_fee": 0,
      "distance_km": 0,
      "c2_status": "ok",
      "c2_threshold": 0,
      "monthly_after": 0,
      "c6_status": "ok",
      "c6_cap": 9000000
    }
  ],
  "unassigned": [],
  "warnings": []
}
```

**results 필드**:

| 필드 | 타입 | 설명 |
|------|------|------|
| `order_id` | string | 주문번호 |
| `model_name` | string | 제품명 (`products` 기반 자동 계산. 단품: `"냉장고 500L"`, 복수: `"냉장고 500L 외 1건"`) |
| `dispatch_type` | string | `"단독"` / `"합배차_주"` / `"합배차_보조"` |
| `driver_id` | string | 배정된 기사 ID |
| `driver_name` | string | 기사명 |
| `secondary_driver_id` | string | 합배차 보조 기사 ID |
| `delivery_sequence` | int | 해당 기사의 배송 순서 (1부터) |
| `scheduled_arrival` | string | 예상 도착 시각 (HH:MM) |
| `install_fee` | int | 설치비 (원) |
| `geometry` | string | 인코딩된 경로 (options.geometry=true 시) |

**driver_summary 필드**:

| 필드 | 타입 | 설명 |
|------|------|------|
| `driver_id` | string | 기사 ID |
| `assigned_count` | int | 배정 건수 |
| `total_fee` | int | 금일 설치비 합계 (원) |
| `distance_km` | float | 총 이동 거리 (km) |
| `c2_status` | string | `"ok"` / `"warning"` 설치비 하한 상태 |
| `c6_status` | string | `"ok"` / `"warning"` / `"over"` 월 수익 상한 상태 |
| `c6_cap` | int | 월 수익 상한 (원, 등급별 차등) |

**unassigned 필드**:

| 필드 | 타입 | 설명 |
|------|------|------|
| `order_id` | string | 미배정 주문번호 |
| `description` | string | 주문번호 (order_id와 동일) |
| `reasons` | array | 미배정 사유 목록 |
| `reasons[].type` | string | 제약 유형 (`"capacity"`, `"skills"`, `"time_window"`, `"complex_constraint"`) |
| `reasons[].description` | string | 한국어 사유 설명 |

**reasons[].type 값**:

| type | 의미 | 해당 HGLIS 제약 |
|------|------|----------------|
| `capacity` | CBM 용량 초과 | C5_CBM |
| `skills` | 기능도 부족 또는 SKU/이력 제약 | C4_GRADE, C7_SKU, C8_HISTORY |
| `time_window` | 희망시간대 충족 불가 | C3_TIME |
| `complex_constraint` | 2인 작업 팀 없음 또는 기타 | C1_CREW |

**HGLIS 비즈니스 제약 (자동 적용)**:

| 제약 | 코드 | 설명 |
|------|------|------|
| 기능도 매칭 | C1 | job.constraints.required_grade ≤ vehicle.grade (S>A>B>C) |
| 설치비 하한 | C2 | 기사 등급별 최소 일 수익 보장 (`fee_status.min_daily_fee` 기준, 0이면 제약 없음) |
| 적재 용량 | C3 | 오더 CBM 합 ≤ vehicle.capacity_cbm |
| 배송 건수 | C4 | 기사 당 최대 건수 (limits.max_orders) |
| 시간대 | C5 | scheduling.preferred_time_slot 기반 time_window |
| 수익 상한 | C6 | 월 수익 상한 — constraint_config.C6.monthly_limit_by_grade |
| 신제품/SKU 회피 | C7 | vehicle.is_rookie × job.products[].is_new_product, exclusions.excluded_skus |
| 미결 이력 | C8 | vehicle.exclusions.avoid_models vs job.products[].sku_code |

#### 비동기 모드 요청

```bash
curl -X POST "http://localhost:8000/dispatch?async=true" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: demo-key-12345" \
  -d '{ ... 동기와 동일한 본문 ... }'
```

**비동기 응답** (즉시):

```json
{
  "job_id": "abc12345-def6-7890-ghij-klmnopqrstuv",
  "status": "queued",
  "poll_url": "/jobs/abc12345-def6-7890-ghij-klmnopqrstuv"
}
```

→ `poll_url`로 진행률 조회 (아래 `/jobs/{job_id}` 참조)

**상태 코드**:

| 코드 | 설명 |
|------|------|
| `200 OK` | 배차 성공 (동기) / 작업 등록 성공 (비동기) |
| `400 Bad Request` | 입력 검증 실패 (모든 오더가 제약 위반 등) |
| `401 Unauthorized` | API Key 누락 또는 유효하지 않음 |
| `422 Unprocessable Entity` | Pydantic 모델 검증 실패 (필드 형식 오류) |
| `429 Too Many Requests` | 요청률 제한 초과 |
| `500 Internal Server Error` | 내부 오류 |

---

### 8. GET /jobs/{job_id} -- 비동기 작업 조회

`/dispatch?async=true`로 시작한 비동기 배차 작업의 진행률과 결과를 조회한다.

> **구현**: Celery + Redis 큐 기반. `dispatch_task.delay()`로 워커에 전달, `AsyncResult(job_id)`로 상태 조회. 워커 2개(각 concurrency=3) — 동시 최대 6건 처리 가능. 워커 상태는 Flower(http://localhost:5555)에서 실시간 확인.

**인증**: 불필요

**요청**:

```bash
curl http://localhost:8000/jobs/abc12345-def6-7890-ghij-klmnopqrstuv
```

**응답 (처리 중)**:

```json
{
  "job_id": "abc12345-def6-7890-ghij-klmnopqrstuv",
  "status": "processing",
  "progress": {
    "stage": "optimizing",
    "stage_label": "최적화 중",
    "percentage": 40
  },
  "elapsed_ms": 2500
}
```

**응답 (완료)**:

```json
{
  "job_id": "abc12345-def6-7890-ghij-klmnopqrstuv",
  "status": "completed",
  "progress": {
    "stage": "completed",
    "stage_label": "완료",
    "percentage": 100
  },
  "elapsed_ms": 5200,
  "result": {
    "status": "success",
    "meta": { ... },
    "statistics": { ... },
    "results": [ ... ],
    "driver_summary": [ ... ],
    "unassigned": [],
    "warnings": []
  }
}
```

**응답 (실패)**:

```json
{
  "job_id": "abc12345-def6-7890-ghij-klmnopqrstuv",
  "status": "failed",
  "progress": {
    "stage": "failed",
    "stage_label": "실패",
    "percentage": 0
  },
  "elapsed_ms": 1800,
  "error": "VROOM binary execution failed"
}
```

**progress.stage 값**:

| stage | percentage | 설명 |
|-------|:----------:|------|
| `queued` | 0% | 대기 중 |
| `validating` | 10% | 입력 검증 중 |
| `preprocessing` | 20% | 전처리 중 (매트릭스 계산, 필터링) |
| `optimizing` | 40% | Pass 1 최적화 중 |
| `optimizing_pass2` | 60% | Pass 2 최적화 중 |
| `retry_relaxation` | 75% | 제약 완화 재시도 중 |
| `postprocessing` | 90% | 후처리 중 (C2/C6 검증, 결과 변환) |
| `completed` | 100% | 완료 |
| `failed` | - | 실패 |

**폴링 권장 간격**: 1~2초

**상태 코드**:

| 코드 | 설명 |
|------|------|
| `200 OK` | 작업 조회 성공 |
| `404 Not Found` | job_id에 해당하는 작업 없음 |

---

### 9. POST /matrix/build -- 청크 매트릭스

OSRM을 이용하여 좌표 간 거리/시간 매트릭스를 생성한다. 대량의 좌표를 75x75 크기의 청크로 분할하여 병렬 처리한다.

**인증**: 필요 (`X-API-Key` 헤더)

**요청 필드**:

| 필드 | 타입 | 필수 | 설명 |
|------|------|:----:|------|
| `locations` | [[lon, lat], ...] | 필수 | 좌표 배열 (경도, 위도) |
| `profile` | string | 선택 | 라우팅 프로파일 (기본: `"driving"`) |

**요청**:

```bash
curl -X POST http://localhost:8000/matrix/build \
  -H "Content-Type: application/json" \
  -H "X-API-Key: demo-key-12345" \
  -d '{
    "locations": [
      [126.9780, 37.5665],
      [127.0276, 37.4979],
      [127.0594, 37.5140],
      [126.9910, 37.5512]
    ],
    "profile": "driving"
  }'
```

**응답 예시**:

```json
{
  "durations": [
    [0, 1200, 1500, 600],
    [1200, 0, 900, 1100],
    [1500, 900, 0, 1300],
    [600, 1100, 1300, 0]
  ],
  "distances": [
    [0, 8500, 11200, 3200],
    [8500, 0, 5600, 7800],
    [11200, 5600, 0, 9500],
    [3200, 7800, 9500, 0]
  ],
  "size": 4,
  "_metadata": {
    "version": "3.0",
    "profile": "driving",
    "chunk_size": 75,
    "processing_time_ms": 350
  }
}
```

---

### 10. POST /map-matching/match -- GPS 궤적 매칭

GPS 궤적을 도로 네트워크에 매칭한다. 정확도가 낮은 구간(20m 초과)만 OSRM Route API로 보정하고, 정확도가 높은 원본 포인트는 보존한다.

**인증**: 필요 (`X-API-Key` 헤더)

**요청 필드**:

| 필드 | 타입 | 필수 | 설명 |
|------|------|:----:|------|
| `trajectory` | array | 필수 | GPS 궤적 포인트 배열 (최소 2개) |
| `enable_debug` | boolean | 선택 | 디버그 정보 포함 여부 (기본: `false`) |

**trajectory 포인트 형식**: `[lon, lat, timestamp, accuracy, speed]`

| 인덱스 | 필드 | 범위 | 설명 |
|:------:|------|------|------|
| 0 | lon | -180 ~ 180 | 경도 |
| 1 | lat | -90 ~ 90 | 위도 |
| 2 | timestamp | Unix epoch (초) | 시간 (시간순 정렬 필수) |
| 3 | accuracy | 0 이상 | GPS 정확도 (미터) |
| 4 | speed | 0 이상 | 속도 (m/s) |

**요청**:

```bash
curl -X POST http://localhost:8000/map-matching/match \
  -H "Content-Type: application/json" \
  -H "X-API-Key: demo-key-12345" \
  -d '{
    "trajectory": [
      [126.9780, 37.5665, 1700000000, 5.0, 10.0],
      [126.9790, 37.5660, 1700000010, 8.0, 12.0],
      [126.9810, 37.5650, 1700000020, 25.0, 11.0],
      [126.9830, 37.5640, 1700000030, 30.0, 13.0],
      [126.9850, 37.5630, 1700000040, 6.0, 10.5],
      [126.9870, 37.5620, 1700000050, 4.0, 11.0]
    ]
  }'
```

**응답 예시**:

```json
{
  "status": "success",
  "message": "맵 매칭이 성공적으로 완료되었습니다",
  "data": {
    "matched_trace": [
      [126.9780, 37.5665, 1700000000, 1.0],
      [126.9790, 37.5660, 1700000010, 1.0],
      [126.9812, 37.5648, 1700000020, 0.5],
      [126.9832, 37.5639, 1700000030, 0.5],
      [126.9850, 37.5630, 1700000040, 1.0],
      [126.9870, 37.5620, 1700000050, 1.0]
    ],
    "summary": {
      "total_points": 6,
      "matched_points": 6
    }
  }
}
```

**matched_trace flag 값**:

| flag | 설명 |
|:----:|------|
| `0.5` | 보정된 포인트 (도로에 스냅됨) |
| `1.0` | 원본 포인트 (변경 없이 유지) |
| `2.0` | 생성된 포인트 (도로를 따라 추가된 중간 포인트) |
| `2.5` | 보간된 포인트 |
| `4.0` | 도로 점프 감지됨 |

---

### 11. GET /map-matching/health -- 맵 매칭 헬스

맵 매칭 서비스의 상태를 확인한다. OSRM 서버 연결을 샘플 경로로 테스트한다.

**인증**: 불필요

```bash
curl http://localhost:8000/map-matching/health
```

```json
{
  "status": "ok",
  "message": "Map matching service is healthy",
  "osrm_url": "http://osrm:5000",
  "osrm_status": "ok",
  "timestamp": "2026-03-01T09:30:00.123456"
}
```

---

### 12. POST /map-matching/validate -- 궤적 검증

GPS 궤적의 품질을 검증한다. 실제 맵 매칭을 수행하지 않고 입력 데이터의 유효성과 품질 지표만 반환한다.

**인증**: 필요 (`X-API-Key` 헤더)

**요청**: `/map-matching/match`와 동일한 형식

**응답 예시**:

```json
{
  "is_valid": true,
  "total_points": 6,
  "quality_score": 0.85,
  "issues": [
    {"type": "low_accuracy", "point_index": 2, "message": "GPS 정확도가 낮습니다 (25.0m)"},
    {"type": "low_accuracy", "point_index": 3, "message": "GPS 정확도가 낮습니다 (30.0m)"}
  ],
  "recommendations": [
    "일부 구간에서 GPS 정확도가 20m를 초과합니다. 매칭 시 해당 구간이 보정됩니다."
  ],
  "metrics": {
    "temporal_consistency": 0.95,
    "spatial_consistency": 1.0,
    "accuracy_distribution": 0.7,
    "speed_consistency": 0.9
  }
}
```

**metrics 설명**:

| 지표 | 설명 | 범위 |
|------|------|------|
| `temporal_consistency` | 시간 순서 및 간격의 일관성 | 0.0 ~ 1.0 |
| `spatial_consistency` | 공간적 연속성 (포인트 간 거리 합리성) | 0.0 ~ 1.0 |
| `accuracy_distribution` | GPS 정확도 분포 (낮은 정확도 비율) | 0.0 ~ 1.0 |
| `speed_consistency` | 속도 값의 일관성 | 0.0 ~ 1.0 |

---

### 13. DELETE /cache/clear -- 캐시 초기화

캐시된 최적화 결과를 모두 삭제한다.

**인증**: 필요 (`X-API-Key` 헤더)

```bash
curl -X DELETE http://localhost:8000/cache/clear \
  -H "X-API-Key: demo-key-12345"
```

```json
{
  "status": "ok",
  "message": "Cache cleared successfully",
  "cleared_entries": 42
}
```

---

### 14. POST /valhalla/distribute -- Valhalla 배차

OSRM 대신 **Valhalla**를 라우팅 백엔드로 사용하는 VROOM 호환 배차 엔드포인트이다. 입출력 포맷은 `/distribute`와 동일하다.

**인증**: 불필요

**OSRM 버전과의 차이점**:
- Valhalla `sources_to_targets` API로 실도로 매트릭스 계산
- Valhalla `/route` API로 실제 도로 geometry 획득
- vehicle profile이 `car` → `auto`로 자동 패치됨 (Valhalla costing method)

**요청**:

```bash
curl -X POST http://localhost:8000/valhalla/distribute \
  -H "Content-Type: application/json" \
  -d '{
    "vehicles": [
      {
        "id": 1,
        "start": [126.9780, 37.5665],
        "end": [126.9780, 37.5665],
        "capacity": [100],
        "skills": [1, 2],
        "time_window": [28800, 64800]
      }
    ],
    "jobs": [
      {
        "id": 101,
        "location": [127.0276, 37.4979],
        "service": 300,
        "delivery": [20],
        "skills": [1],
        "time_windows": [[32400, 36000]]
      }
    ]
  }'
```

**응답 예시**:

```json
{
  "code": 0,
  "summary": {
    "cost": 1234,
    "routes": 1,
    "unassigned": 0,
    "service": 300,
    "duration": 2400,
    "distance": 12500
  },
  "routes": [
    {
      "vehicle": 1,
      "steps": [
        {"type": "start", "location": [126.9780, 37.5665], "arrival": 28800},
        {"type": "job", "id": 101, "location": [127.0276, 37.4979], "arrival": 32400, "service": 300},
        {"type": "end", "location": [126.9780, 37.5665], "arrival": 35400}
      ],
      "geometry": "encoded_polyline_string..."
    }
  ],
  "unassigned": [],
  "_wrapper": {
    "version": "3.0.0",
    "engine": "valhalla",
    "processing_time_ms": 320
  }
}
```

**geometry 제어**: `"options": {"g": true}` 포함 시 응답에 geometry 유지. 미지정 시 내부적으로 geometry를 요청하되 응답에서 제거.

**상태 코드**:

| 코드 | 설명 |
|------|------|
| `200 OK` | 최적화 성공 |
| `400 Bad Request` | 잘못된 입력 |
| `500 Internal Server Error` | VROOM/Valhalla 실행 오류 |
| `503 Service Unavailable` | Valhalla 서버 미가동 |

---

### 15. POST /valhalla/optimize -- Valhalla 표준 최적화

Valhalla 라우팅 기반 2-Pass 표준 최적화. OSRM `/optimize`와 동일한 파이프라인을 Valhalla로 실행하며 시간대별 ETA가 보정된다.

**처리 순서**: 전처리 → Valhalla 매트릭스 사전 계산 → 도달 불가 필터링 → VROOM 2-Pass 최적화 → 미배정 자동 재시도 → **ETA 보정 (Valhalla)** → 분석 → 통계 → 캐싱

**인증**: 필요 (`X-API-Key` 헤더)

**추가 입력 필드** (VROOM 표준 필드 외):

| 필드 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| `use_cache` | boolean | `true` | 캐시 사용 여부 |
| `business_rules` | object | `null` | 비즈니스 규칙 설정 |

**요청**:

```bash
curl -X POST http://localhost:8000/valhalla/optimize \
  -H "Content-Type: application/json" \
  -H "X-API-Key: demo-key-12345" \
  -d '{
    "vehicles": [
      {
        "id": 1,
        "start": [126.9780, 37.5665],
        "end": [126.9780, 37.5665],
        "capacity": [100],
        "skills": [1, 2],
        "time_window": [28800, 64800],
        "max_tasks": 10
      }
    ],
    "jobs": [
      {
        "id": 101,
        "location": [127.0276, 37.4979],
        "service": 300,
        "delivery": [20],
        "skills": [1],
        "priority": 100,
        "time_windows": [[32400, 36000]]
      },
      {
        "id": 102,
        "location": [127.0594, 37.5140],
        "service": 600,
        "delivery": [30],
        "skills": [2],
        "time_windows": [[43200, 50400]]
      }
    ],
    "use_cache": true
  }'
```

**응답 예시**:

```json
{
  "wrapper_version": "3.0.0",
  "routes": [
    {
      "vehicle": 1,
      "cost": 1400,
      "service": 600,
      "duration": 4800,
      "distance": 18500,
      "steps": [
        {"type": "start", "location": [126.9780, 37.5665], "arrival": 28800},
        {"type": "job", "id": 101, "location": [127.0276, 37.4979], "arrival": 32400, "service": 300},
        {"type": "end", "location": [126.9780, 37.5665], "arrival": 35400}
      ],
      "geometry": "encoded_polyline_string..."
    }
  ],
  "summary": {
    "cost": 1400,
    "routes": 1,
    "unassigned": 1,
    "service": 600,
    "duration": 4800,
    "distance": 18500
  },
  "unassigned": [
    {
      "id": 102,
      "reasons": [{"type": "skills", "description": "No vehicle has required skills"}]
    }
  ],
  "analysis": {
    "quality_score": 0.85,
    "vehicle_utilization": [{"vehicle_id": 1, "utilization": 0.75, "tasks": 1}]
  },
  "statistics": {
    "distances": {"total": 18500, "per_vehicle": [18500]},
    "durations": {"total": 4800, "per_vehicle": [4800]}
  },
  "_metadata": {
    "api_key": "demo",
    "control_level": "STANDARD",
    "engine": "valhalla",
    "processing_time_ms": 980,
    "from_cache": false
  }
}
```

**상태 코드**:

| 코드 | 설명 |
|------|------|
| `200 OK` | 최적화 성공 |
| `400 Bad Request` | 잘못된 입력 |
| `401 Unauthorized` | API Key 누락 또는 유효하지 않음 |
| `429 Too Many Requests` | 요청률 제한 초과 |
| `500 Internal Server Error` | 내부 오류 |
| `503 Service Unavailable` | Valhalla 서버 미가동 |

---

### 16. POST /valhalla/optimize/basic -- Valhalla 기본 최적화

분석(analysis)·통계(statistics)·재시도 단계를 생략한 Valhalla 1-Pass 경량 최적화 + ETA 보정. 빠른 결과가 필요할 때 사용한다.

**인증**: 필요 (`X-API-Key` 헤더)

**요청**: `/valhalla/optimize`와 동일한 입력 형식

```bash
curl -X POST http://localhost:8000/valhalla/optimize/basic \
  -H "Content-Type: application/json" \
  -H "X-API-Key: demo-key-12345" \
  -d '{
    "vehicles": [
      {"id": 1, "start": [126.9780, 37.5665], "end": [126.9780, 37.5665], "capacity": [100]}
    ],
    "jobs": [
      {"id": 101, "location": [127.0276, 37.4979], "service": 300, "delivery": [20]},
      {"id": 102, "location": [127.0594, 37.5140], "service": 600, "delivery": [30]}
    ]
  }'
```

**응답**: `analysis`, `statistics` 필드 없이 `wrapper_version`, `routes`, `summary`, `unassigned`, `_metadata`만 포함.

```json
{
  "wrapper_version": "3.0.0",
  "routes": [...],
  "summary": {...},
  "unassigned": [],
  "_metadata": {
    "api_key": "demo",
    "engine": "valhalla",
    "control_level": "BASIC"
  }
}
```

**상태 코드**:

| 코드 | 설명 |
|------|------|
| `200 OK` | 최적화 성공 |
| `401 Unauthorized` | API Key 누락 또는 유효하지 않음 |
| `500 Internal Server Error` | 내부 오류 |
| `503 Service Unavailable` | Valhalla 서버 미가동 |

---

### 17. POST /valhalla/optimize/premium -- Valhalla 프리미엄 최적화

Valhalla 매트릭스 선계산 + **3-시나리오 병렬 실행 → 최적해 선택 + ETA 보정**을 지원하는 프리미엄 엔드포인트이다. VROOM+Valhalla 계열 중 최고 품질.

**인증**: 필요 (`X-API-Key` 헤더, Premium 권한)

**요청률 제한**: 50 요청 / 3600초

**요청**: `/valhalla/optimize`와 동일한 입력 형식

```bash
curl -X POST http://localhost:8000/valhalla/optimize/premium \
  -H "Content-Type: application/json" \
  -H "X-API-Key: demo-key-12345" \
  -d '{
    "vehicles": [
      {"id": 1, "start": [126.9780, 37.5665], "end": [126.9780, 37.5665], "capacity": [100], "max_tasks": 10},
      {"id": 2, "start": [127.0594, 37.5140], "end": [127.0594, 37.5140], "capacity": [200]}
    ],
    "jobs": [
      {"id": 101, "location": [127.0276, 37.4979], "service": 300, "delivery": [20]},
      {"id": 102, "location": [127.0594, 37.5140], "service": 600, "delivery": [30]},
      {"id": 103, "location": [126.9910, 37.5512], "service": 300, "delivery": [15]},
      {"id": 104, "location": [127.0100, 37.5300], "service": 300, "delivery": [10]},
      {"id": 105, "location": [127.0200, 37.5100], "service": 600, "delivery": [25]},
      {"id": 106, "location": [126.9900, 37.5600], "service": 300, "delivery": [20]},
      {"id": 107, "location": [127.0400, 37.5000], "service": 300, "delivery": [15]},
      {"id": 108, "location": [127.0300, 37.5200], "service": 600, "delivery": [30]},
      {"id": 109, "location": [126.9800, 37.5400], "service": 300, "delivery": [10]},
      {"id": 110, "location": [127.0500, 37.5050], "service": 300, "delivery": [20]}
    ]
  }'
```

**응답 예시**:

```json
{
  "wrapper_version": "3.0.0",
  "routes": [...],
  "summary": {
    "cost": 4200,
    "routes": 2,
    "unassigned": 0,
    "duration": 14400,
    "distance": 52000
  },
  "unassigned": [],
  "analysis": {
    "quality_score": 0.94,
    "vehicle_utilization": [
      {"vehicle_id": 1, "utilization": 0.90, "tasks": 5},
      {"vehicle_id": 2, "utilization": 0.85, "tasks": 5}
    ]
  },
  "statistics": {
    "distances": {"total": 52000, "per_vehicle": [26000, 26000]},
    "durations": {"total": 14400, "per_vehicle": [7200, 7200]}
  },
  "_metadata": {
    "api_key": "demo",
    "engine": "valhalla",
    "control_level": "PREMIUM",
    "two_pass": true,
    "processing_time_ms": 2100
  }
}
```

**2-Pass 동작**: job + shipment 합계가 10개 이상일 때 자동 활성화. Pass 1에서 배정을 결정하고, Pass 2에서 경로 순서를 최적화한다. 10개 미만이면 단일 실행.

**상태 코드**:

| 코드 | 설명 |
|------|------|
| `200 OK` | 최적화 성공 |
| `401 Unauthorized` | API Key 누락 또는 유효하지 않음 |
| `403 Forbidden` | Premium 권한 없음 |
| `429 Too Many Requests` | 요청률 제한 초과 |
| `500 Internal Server Error` | 내부 오류 |
| `503 Service Unavailable` | Valhalla 서버 미가동 |

---

## 요청 형식

### VROOM 표준 (Vehicles, Jobs, Shipments)

`/distribute`, `/optimize`, `/optimize/basic`, `/optimize/premium`, `/valhalla/distribute`, `/valhalla/optimize`, `/valhalla/optimize/basic`, `/valhalla/optimize/premium` 엔드포인트에서 사용한다.

#### 기본 구조

```json
{
  "vehicles": [...],
  "jobs": [...],
  "shipments": [...],
  "options": {"g": true}
}
```

#### Vehicles (차량)

```json
{
  "id": 1,
  "start": [126.9780, 37.5665],
  "end": [126.9780, 37.5665],
  "capacity": [100, 50],
  "skills": [1, 2, 3],
  "time_window": [28800, 64800],
  "max_tasks": 10,
  "speed_factor": 1.0,
  "breaks": [
    {"id": 1, "time_windows": [[43200, 46800]], "service": 3600}
  ]
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|:----:|------|
| `id` | integer | 필수 | 차량 고유 ID |
| `start` | [lon, lat] | 필수 | 시작 위치 |
| `end` | [lon, lat] | 선택 | 종료 위치 (없으면 start와 동일) |
| `capacity` | [int, ...] | 선택 | 용량 (다차원 가능) |
| `skills` | [int, ...] | 선택 | 보유 기술 목록 |
| `time_window` | [start, end] | 선택 | 근무 시간 (초 단위 또는 UNIX timestamp) |
| `max_tasks` | integer | 선택 | 최대 배정 작업 수 |
| `speed_factor` | float | 선택 | 속도 계수 (기본 1.0) |
| `breaks` | array | 선택 | 휴식 시간 설정 |

**시간 변환 참고**: `08:00 = 28800초`, `12:00 = 43200초`, `18:00 = 64800초`

#### Jobs (작업)

```json
{
  "id": 101,
  "location": [127.0276, 37.4979],
  "service": 300,
  "delivery": [10, 5],
  "pickup": [5, 2],
  "skills": [1, 3],
  "priority": 100,
  "time_windows": [[32400, 36000], [43200, 46800]]
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|:----:|------|
| `id` | integer | 필수 | 작업 고유 ID |
| `location` | [lon, lat] | 필수 | 작업 위치 |
| `service` | integer | 선택 | 작업 소요 시간 (초, 기본 300) |
| `delivery` | [int, ...] | 선택 | 배송량 (capacity와 차원 일치) |
| `pickup` | [int, ...] | 선택 | 픽업량 |
| `skills` | [int, ...] | 선택 | 필요 기술 (모두 충족해야 배정) |
| `priority` | integer | 선택 | 우선순위 (0-100, 높을수록 우선) |
| `time_windows` | array | 선택 | 가능 시간대 (여러 개 가능) |

#### Shipments (픽업-배송 쌍)

```json
{
  "id": 1,
  "pickup": {
    "id": 1,
    "location": [127.0276, 37.4979],
    "service": 300,
    "time_windows": [[28800, 36000]]
  },
  "delivery": {
    "id": 2,
    "location": [127.0594, 37.5140],
    "service": 300,
    "time_windows": [[36000, 43200]]
  },
  "amount": [10],
  "skills": [1]
}
```

### HGLIS 형식 (HglisVehicle, HglisJob)

`/dispatch` 엔드포인트에서 사용한다. 상세 필드는 [POST /dispatch](#7-post-dispatch---hglis-배차) 섹션 참조.

---

## 응답 형식

### 공통 응답 구조 (VROOM 호환 엔드포인트)

`/distribute`, `/optimize` 계열 엔드포인트의 응답:

```json
{
  "code": 0,
  "summary": {"cost": 0, "routes": 0, "unassigned": 0, "distance": 0, "duration": 0},
  "routes": [...],
  "unassigned": [...]
}
```

| 필드 | 설명 |
|------|------|
| `code` | VROOM 결과 코드 (0: 성공) |
| `summary` | 전체 요약 (비용, 경로 수, 미배정 수, 거리, 소요 시간) |
| `routes` | 차량별 경로 및 단계 (steps) |
| `unassigned` | 미배정 작업 목록 및 사유 |

### 엔드포인트별 추가 응답 필드

| 엔드포인트 | 추가 필드 |
|------------|-----------|
| `/distribute` | `_wrapper` |
| `/optimize` | `analysis`, `statistics`, `_metadata` |
| `/optimize/basic` | `_metadata` |
| `/optimize/premium` | `analysis`, `statistics`, `multi_scenario_metadata`, `_metadata` |
| `/dispatch` | `results`, `driver_summary`, `unassigned`, `warnings` (HGLIS 전용 구조) |

### 미배정 사유 유형

`/distribute`, `/optimize` 계열이 반환하는 `reasons` 배열:

| type | 설명 | 정확도 |
|------|------|:------:|
| `skills` | 필요한 기술을 보유한 차량이 없음 | 100% |
| `capacity` | 작업 물량이 모든 차량의 용량을 초과 | 100% |
| `time_window` | 작업 시간대가 모든 차량의 근무 시간과 불일치 | 95% |
| `max_tasks` | 모든 차량의 최대 작업 수 초과 | 90% |
| `vehicle_time_window` | 차량 근무 시간과 불일치 | 95% |
| `no_vehicles` | 사용 가능한 차량 없음 | 100% |
| `unreachable` | OSRM에서 도달 불가능 판정 | 100% |
| `complex_constraint` | 복합 제약 (최적화 과정에서 배제) | 70% |

`/dispatch` 엔드포인트는 HGLIS 제약 코드로 반환:

| constraint | 설명 |
|------------|------|
| `C1_skill` | 기능도 미달 |
| `C3_capacity` | 적재 용량 초과 |
| `C5_time` | 시간대 불일치 |
| `C7_new_product` | 신제품 제한 |
| `C8_avoid` | 미결 이력 회피 |
| `region_mismatch` | 권역 불일치 |

### 분석 및 통계

`/optimize` 및 `/optimize/premium` 엔드포인트가 반환하는 추가 정보:

**analysis**:

| 필드 | 타입 | 설명 |
|------|------|------|
| `quality_score` | float | 최적화 품질 점수 (0.0 ~ 1.0) |
| `suggestions` | [string] | 개선 제안 목록 |
| `vehicle_utilization` | array | 차량별 활용률 |

**statistics**:

| 필드 | 설명 |
|------|------|
| `distances.total` | 전체 이동 거리 (미터) |
| `distances.per_vehicle` | 차량별 이동 거리 |
| `durations.total` | 전체 소요 시간 (초) |
| `durations.per_vehicle` | 차량별 소요 시간 |
| `averages.distance_per_task` | 작업당 평균 이동 거리 |
| `averages.duration_per_task` | 작업당 평균 소요 시간 |

---

## 에러 코드

### 에러 응답 형식

```json
{"detail": "에러 메시지"}
```

Pydantic 검증 실패 (422):

```json
{
  "detail": [
    {
      "type": "value_error",
      "loc": ["body", "jobs", 0, "region_code"],
      "msg": "Value error, 유효하지 않은 권역코드: R01 (허용: Y1, Y2, ...)",
      "input": "R01"
    }
  ]
}
```

### 상태 코드 종합

| 상태 코드 | 설명 | 원인 |
|-----------|------|------|
| `200 OK` | 요청 성공 | - |
| `400 Bad Request` | 잘못된 입력 | vehicles 없음, jobs 없음, 필수 필드 누락 |
| `401 Unauthorized` | 인증 실패 | API Key 누락 또는 유효하지 않은 키 |
| `403 Forbidden` | 권한 부족 | 프리미엄 기능 권한 없음 |
| `404 Not Found` | 리소스 없음 | job_id 미존재 |
| `422 Unprocessable Entity` | 입력 검증 실패 | 필드 타입 오류, 권역코드 오류, 좌표 범위 초과 |
| `429 Too Many Requests` | 요청률 초과 | API Key별 요청 제한 초과 |
| `500 Internal Server Error` | 내부 오류 | VROOM 실행 오류, OSRM 연결 오류 |
| `503 Service Unavailable` | 서비스 이용 불가 | OSRM 또는 핵심 컴포넌트 장애 |

---

## 환경 변수

### VROOM 바이너리

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `USE_DIRECT_CALL` | `true` | VROOM 바이너리 직접 호출 |
| `VROOM_BINARY_PATH` | `/usr/local/bin/vroom` | VROOM 바이너리 경로 |
| `VROOM_ROUTER` | `osrm` | 라우팅 엔진 |
| `VROOM_THREADS` | `4` | VROOM 기본 스레드 수 |
| `VROOM_EXPLORATION` | `5` | VROOM 탐색 강도 (높을수록 정밀, 느림) |
| `VROOM_TIMEOUT` | `300` | VROOM 실행 타임아웃 (초) |

### OSRM

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `OSRM_URL` | `http://osrm:5000` | OSRM 서버 URL |
| `OSRM_CHUNK_SIZE` | `75` | 매트릭스 청크 크기 (75x75) |
| `OSRM_MAX_WORKERS` | `8` | 매트릭스 병렬 처리 워커 수 |

### 최적화 파이프라인

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `TWO_PASS_ENABLED` | `true` | 2-Pass 최적화 활성화 |
| `TWO_PASS_MAX_WORKERS` | `4` | Pass 2 병렬 워커 수 |
| `TWO_PASS_INITIAL_THREADS` | `16` | Pass 1 (배정) 스레드 수 |
| `TWO_PASS_ROUTE_THREADS` | `4` | Pass 2 (경로 최적화) 스레드 수 |
| `MATRIX_PREP_ENABLED` | `true` | OSRM 매트릭스 사전 계산 (HGLIS 파이프라인) |
| `UNREACHABLE_FILTER_ENABLED` | `true` | 도달 불가 작업 사전 필터링 |
| `UNREACHABLE_THRESHOLD` | `43200` | 도달 불가 판정 기준 (초, 기본 12시간) |

### Celery 비동기 큐

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `REDIS_URL` | `redis://redis:6379` | Redis URL (Celery broker + backend, 캐시 겸용) |
| `MAX_CONCURRENT_DISPATCH` | `3` | Wrapper 동기 모드 동시 실행 제한 (Celery와 별개) |

### 캐시

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `REDIS_URL` | `redis://redis:6379` | Redis 접속 URL (미연결 시 인메모리 폴백) |

### 맵 매칭

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `MAP_MATCHING_ENABLED` | `true` | 맵 매칭 모듈 활성화 |

### 서버

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `HOST` | `0.0.0.0` | 서버 바인딩 호스트 |
| `PORT` | `8000` | 서버 바인딩 포트 |
| `LOG_LEVEL` | `INFO` | 로그 레벨 (DEBUG, INFO, WARNING, ERROR) |

### 요청률 제한

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `RATE_LIMIT_ENABLED` | `true` | 요청률 제한 활성화 |
| `RATE_LIMIT_REQUESTS` | `100` | 기간 내 최대 요청 수 |
| `RATE_LIMIT_WINDOW` | `3600` | 제한 기간 (초) |

---

## Docker 배포

### 서비스 구성

| 서비스 | 포트 | 설명 |
|--------|------|------|
| OSRM | `:5000` | MLD 알고리즘 도로 라우팅 엔진 |
| Valhalla | `:8002` | time-dependent 라우팅 엔진 (한국 전체) |
| Redis | `:6379` | 캐시 + Celery 브로커/백엔드 |
| Wrapper | `:8000` | VROOM Wrapper API 서버 + VROOM 바이너리 |
| celery-worker (×2) | — | 비동기 dispatch 처리 워커 (각 concurrency=3, 총 동시 6건) |
| Flower | `:5555` | Celery 모니터링 웹 UI (http://localhost:5555, admin/hglis2024) |

### 실행

```bash
# 시작
docker compose -f docker-compose.v3.yml up -d

# 빌드 후 시작
docker compose -f docker-compose.v3.yml up --build -d

# 중지
docker compose -f docker-compose.v3.yml down
```

### 상태 확인

```bash
# 서비스 상태
docker compose -f docker-compose.v3.yml ps

# 헬스 체크
curl http://localhost:8000/health

# Wrapper 로그
docker logs vroom-wrapper-v3 --tail 50

# Celery 워커 로그 (처리 중인 dispatch 확인)
docker logs vroom-celery-worker --tail 50
docker logs vroom-celery-worker-2 --tail 50

# 2-Pass 동작 확인
docker logs vroom-celery-worker 2>&1 | grep -E "PASS 1|PASS 2|MATRIX_PREP|FILTER"

# Celery 모니터링 웹 UI
http://localhost:5555  # admin / hglis2024
```

### OSRM 데이터 준비

```bash
# 한국 지도 데이터 위치
/home/shawn/osrm-data/south-korea-latest.osrm

# OSRM 알고리즘: MLD (Multi-Level Dijkstra)
# max-table-size: 10000 (매트릭스 최대 크기)
```

---

## 버전 이력

### v3.1.2 (2026-03-15)

- **Celery 워커 2개** (worker1@vroom-worker-1, worker2@vroom-worker-2): 동시 6건 비동기 dispatch 처리
- **Flower 모니터링** (`:5555`): 워커 상태, 태스크 큐, 처리 이력 웹 UI
- **`UnassignedJob.reasons[]` 버그 수정**: ConstraintChecker 분석 결과가 응답에 정상 반영됨
  - `reason: str` (기존 유지) + `reasons: List[Dict]` 추가 (상세 사유 배열)

### v3.1.1 (2026-03-14)

- **Celery + Redis 큐 도입**: 비동기 dispatch 백엔드를 FastAPI BackgroundTasks → Celery로 전환
- **`unassigned[].reasons[]` 구조 변경** ⚠️ Breaking Change: `reason: str` → `reasons: [{type, description}]` 배열
- **`results[].model_name`**: products 기반 자동 계산 (`"소파 3인용 외 1건"` 형식)

### v3.1 (2026-03)

- **HGLIS 배차 엔진** (`POST /dispatch`): C1~C8 비즈니스 제약 통합
- **비동기 배차** (`?async=true` + `GET /jobs/{job_id}`): 진행률 실시간 조회
- **2-Pass 최적화 활성화**: Pass 1 배정(threads=16) → Pass 2 경로 최적화(threads=4, 병렬)
- **OSRM 매트릭스 사전 계산**: HGLIS 파이프라인에서 OSRM 1회 호출, 서브매트릭스 재활용
- **도달 불가능 필터**: 매트릭스 기반 사전 필터링 활성화
- **HGLIS 제약**: 기능도(C1), 설치비(C2), 적재(C3), 건수(C4), 시간(C5), 수익상한(C6), 신제품(C7), 미결이력(C8)
- **권역 매칭**: strict / flexible / ignore 모드
- **기사 요약**: C2/C6 상태, 설치비, 이동거리 통합 리포트

### v3.0 (2025-02)

- VROOM 바이너리 직접 호출 (vroom-express 제거)
- 2-Pass 최적화 구현 (비활성 상태)
- 도달 불가 작업 필터 구현 (`unreachable` 사유)
- OSRM 청크 매트릭스 빌더 (`/matrix/build`)
- GPS 맵 매칭 모듈 (`/map-matching/*`)

### v2.0 (2024)

- API Key 인증, 요청률 제한
- Redis 캐싱
- VIP/긴급 비즈니스 규칙
- 다단계 최적화 (basic/standard/premium)
- 제약 완화 자동 재시도
- 멀티 시나리오 최적화
- 품질 점수 및 통계

### v1.0 (2024-01)

- 초기 릴리스, 기본 최적화, 미배정 사유 분석

---

## 문의 및 지원

- **VROOM 공식 문서**: https://github.com/VROOM-Project/vroom/wiki
- **OSRM 공식 문서**: https://project-osrm.org/docs/v5.24.0/api/
- **FastAPI 자동 문서**: `http://localhost:8000/docs` (Swagger UI)
