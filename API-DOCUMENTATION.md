# VROOM Wrapper v3.0 API 문서

VRP(Vehicle Routing Problem) 최적화 플랫폼 - Python FastAPI 기반 VROOM C++ 바이너리 래퍼

---

## 목차

1. [기본 정보](#기본-정보)
   - [Base URL](#base-url)
   - [인증](#인증)
   - [요청률 제한](#요청률-제한)
2. [엔드포인트 목록](#엔드포인트-목록)
3. [엔드포인트 상세](#엔드포인트-상세)
   - [GET / - 루트](#1-get----루트)
   - [GET /health - 헬스 체크](#2-get-health---헬스-체크)
   - [POST /distribute - VROOM 호환](#3-post-distribute---vroom-호환)
   - [POST /optimize - 표준 최적화](#4-post-optimize---표준-최적화)
   - [POST /optimize/basic - 기본 최적화](#5-post-optimizebasic---기본-최적화)
   - [POST /optimize/premium - 프리미엄 최적화](#6-post-optimizepremium---프리미엄-최적화)
   - [POST /matrix/build - 청크 매트릭스](#7-post-matrixbuild---청크-매트릭스)
   - [POST /map-matching/match - GPS 궤적 매칭](#8-post-map-matchingmatch---gps-궤적-매칭)
   - [GET /map-matching/health - 맵 매칭 헬스](#9-get-map-matchinghealth---맵-매칭-헬스)
   - [POST /map-matching/validate - 궤적 검증](#10-post-map-matchingvalidate---궤적-검증)
   - [DELETE /cache/clear - 캐시 초기화](#11-delete-cacheclear---캐시-초기화)
4. [요청 형식](#요청-형식)
   - [Vehicles (차량)](#vehicles-차량)
   - [Jobs (작업)](#jobs-작업)
   - [Shipments (픽업-배송 쌍)](#shipments-픽업-배송-쌍)
5. [응답 형식](#응답-형식)
   - [미배정 사유 유형](#미배정-사유-유형)
   - [분석 및 통계](#분석-및-통계)
6. [에러 코드](#에러-코드)
7. [환경 변수](#환경-변수)
8. [Docker 배포](#docker-배포)
9. [버전 이력](#버전-이력)

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

### 아키텍처

v3.0은 vroom-express(Node.js HTTP 서버)를 제거하고, VROOM C++ 바이너리를 subprocess로 직접 호출한다.
도로 기반 라우팅은 OSRM을 사용하며, 캐싱은 Redis(선택, 미사용 시 인메모리 폴백)를 지원한다.

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
| `POST /matrix/build` | 필요 |
| `POST /map-matching/match` | 필요 |
| `GET /map-matching/health` | 불필요 |
| `POST /map-matching/validate` | 필요 |
| `DELETE /cache/clear` | 필요 |

### 요청률 제한

API Key 단위로 요청률 제한(Rate Limiting)이 적용된다.

| 구분 | 제한 | 기간 |
|------|------|------|
| 기본 엔드포인트 | 100 요청 | 3600초 (1시간) |
| 프리미엄 엔드포인트 | 50 요청 | 3600초 (1시간) |

제한 초과 시 HTTP `429 Too Many Requests` 응답이 반환된다.

```json
{
  "detail": "Rate limit exceeded. Try again later."
}
```

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
| 7 | POST | `/matrix/build` | OSRM 청크 매트릭스 생성 | 필요 |
| 8 | POST | `/map-matching/match` | GPS 궤적 맵 매칭 | 필요 |
| 9 | GET | `/map-matching/health` | 맵 매칭 서비스 헬스 체크 | 불필요 |
| 10 | POST | `/map-matching/validate` | 궤적 품질 검증 | 필요 |
| 11 | DELETE | `/cache/clear` | 캐시 전체 초기화 | 필요 |

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
  "service": "VROOM Wrapper",
  "version": "3.0",
  "description": "VRP optimization platform",
  "endpoints": [
    "/",
    "/health",
    "/distribute",
    "/optimize",
    "/optimize/basic",
    "/optimize/premium",
    "/matrix/build",
    "/map-matching/match",
    "/map-matching/health",
    "/map-matching/validate",
    "/cache/clear"
  ]
}
```

**상태 코드**:

| 코드 | 설명 |
|------|------|
| `200 OK` | 정상 응답 |

---

### 2. GET /health -- 헬스 체크

서비스 구성 요소의 상태를 반환한다. VROOM 바이너리, 2-Pass 최적화, 도달 불가 필터, 캐시, 맵 매칭 등 각 컴포넌트의 동작 여부를 확인할 수 있다.

**인증**: 불필요

**요청**:

```bash
curl http://localhost:8000/health
```

**응답 예시**:

```json
{
  "status": "ok",
  "components": {
    "vroom_binary": "ok",
    "two_pass": "disabled",
    "unreachable_filter": "ok",
    "cache": "ok",
    "map_matching": "ok"
  }
}
```

**상태 코드**:

| 코드 | 설명 |
|------|------|
| `200 OK` | 모든 핵심 서비스 정상 |
| `503 Service Unavailable` | 핵심 컴포넌트 이상 |

---

### 3. POST /distribute -- VROOM 호환

VROOM 표준 JSON 형식을 그대로 사용하는 호환 엔드포인트이다. API Key 없이 사용할 수 있다.
VROOM C++ 바이너리를 직접 호출하며, OSRM을 통해 항상 geometry를 요청하여 정확한 거리 정보를 얻는다.

Wrapper가 추가하는 필드:
- `unassigned[].reasons` : 미배정 사유 분석 결과
- `_wrapper` : 래퍼 메타데이터

**인증**: 불필요

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
    "version": "3.0",
    "mode": "distribute"
  }
}
```

**상태 코드**:

| 코드 | 설명 |
|------|------|
| `200 OK` | 최적화 성공 |
| `400 Bad Request` | 잘못된 입력 (vehicles/jobs 누락 등) |
| `500 Internal Server Error` | VROOM 바이너리 실행 오류 또는 내부 오류 |

---

### 4. POST /optimize -- 표준 최적화

전체 파이프라인을 실행하는 표준 최적화 엔드포인트이다.

**처리 순서**: 전처리 -> 도달 불가 작업 필터링 -> VROOM 최적화 -> 제약 완화 자동 재시도 -> 분석 -> 통계 -> 캐싱

**인증**: 필요 (`X-API-Key` 헤더)

**추가 입력 필드** (VROOM 표준 필드 외):

| 필드 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| `use_cache` | boolean | `true` | 캐시 사용 여부 |
| `business_rules` | object | `null` | 비즈니스 규칙 설정 |
| `business_rules.vip_job_ids` | [int] | `[]` | VIP 작업 ID 목록 |
| `business_rules.urgent_job_ids` | [int] | `[]` | 긴급 작업 ID 목록 |
| `business_rules.enable_vip` | boolean | `false` | VIP 규칙 활성화 |
| `business_rules.enable_urgent` | boolean | `false` | 긴급 규칙 활성화 |

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
      "urgent_job_ids": [],
      "enable_vip": true,
      "enable_urgent": false
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
          "type": "job",
          "id": 103,
          "location": [126.9910, 37.5512],
          "arrival": 50400,
          "duration": 21600,
          "service": 300,
          "load": [35]
        },
        {
          "type": "end",
          "location": [126.9780, 37.5665],
          "arrival": 51900,
          "duration": 23100
        }
      ],
      "violations": [],
      "geometry": "encoded_polyline_string..."
    },
    {
      "vehicle": 2,
      "cost": 1450,
      "service": 600,
      "duration": 4800,
      "distance": 16700,
      "steps": [
        {
          "type": "start",
          "location": [127.0594, 37.5140],
          "arrival": 36000,
          "duration": 0
        },
        {
          "type": "job",
          "id": 102,
          "location": [127.0594, 37.5140],
          "arrival": 43200,
          "duration": 7200,
          "service": 600,
          "load": [30]
        },
        {
          "type": "end",
          "location": [127.0594, 37.5140],
          "arrival": 44400,
          "duration": 8400
        }
      ],
      "violations": [],
      "geometry": "encoded_polyline_string..."
    }
  ],
  "unassigned": [],
  "analysis": {
    "quality_score": 0.92,
    "suggestions": [
      "차량 1의 대기 시간이 길어 경로 재배치를 고려하세요"
    ],
    "vehicle_utilization": [
      {
        "vehicle_id": 1,
        "utilization": 0.85,
        "tasks": 2
      },
      {
        "vehicle_id": 2,
        "utilization": 0.65,
        "tasks": 1
      }
    ]
  },
  "statistics": {
    "distances": {
      "total": 35200,
      "per_vehicle": [18500, 16700]
    },
    "durations": {
      "total": 9600,
      "per_vehicle": [4800, 4800]
    },
    "averages": {
      "distance_per_task": 11733,
      "duration_per_task": 3200
    }
  },
  "_metadata": {
    "version": "3.0",
    "mode": "optimize",
    "pipeline": ["preprocessing", "unreachable_filter", "vroom", "analysis", "statistics"],
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

**요청**:

```bash
curl -X POST http://localhost:8000/optimize/basic \
  -H "Content-Type: application/json" \
  -H "X-API-Key: demo-key-12345" \
  -d '{
    "vehicles": [
      {
        "id": 1,
        "start": [126.9780, 37.5665],
        "end": [126.9780, 37.5665],
        "capacity": [100]
      }
    ],
    "jobs": [
      {
        "id": 101,
        "location": [127.0276, 37.4979],
        "service": 300,
        "delivery": [20]
      },
      {
        "id": 102,
        "location": [127.0594, 37.5140],
        "service": 600,
        "delivery": [30]
      }
    ]
  }'
```

**응답 예시**:

```json
{
  "code": 0,
  "summary": {
    "cost": 1580,
    "routes": 1,
    "unassigned": 0,
    "service": 900,
    "duration": 3600,
    "waiting_time": 0,
    "distance": 19500,
    "violations": []
  },
  "routes": [
    {
      "vehicle": 1,
      "cost": 1580,
      "service": 900,
      "duration": 3600,
      "distance": 19500,
      "steps": [
        {"type": "start", "location": [126.9780, 37.5665], "arrival": 0, "duration": 0},
        {"type": "job", "id": 102, "location": [127.0594, 37.5140], "arrival": 900, "duration": 900, "service": 600, "load": [30]},
        {"type": "job", "id": 101, "location": [127.0276, 37.4979], "arrival": 2100, "duration": 2100, "service": 300, "load": [50]},
        {"type": "end", "location": [126.9780, 37.5665], "arrival": 3600, "duration": 3600}
      ],
      "violations": [],
      "geometry": "encoded_polyline_string..."
    }
  ],
  "unassigned": [],
  "_metadata": {
    "version": "3.0",
    "mode": "optimize/basic",
    "processing_time_ms": 420
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

### 6. POST /optimize/premium -- 프리미엄 최적화

멀티 시나리오 비교와 2-Pass 최적화를 지원하는 프리미엄 엔드포인트이다. API Key에 프리미엄 권한이 있어야 사용할 수 있다.

표준 최적화의 모든 기능에 더해 멀티 시나리오 메타데이터가 응답에 포함된다.

**인증**: 필요 (`X-API-Key` 헤더, 프리미엄 권한)

**요청률 제한**: 50 요청 / 3600초

**요청**:

```bash
curl -X POST http://localhost:8000/optimize/premium \
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
      "urgent_job_ids": [103],
      "enable_vip": true,
      "enable_urgent": true
    }
  }'
```

**응답 예시**:

```json
{
  "code": 0,
  "summary": {
    "cost": 2750,
    "routes": 2,
    "unassigned": 0,
    "service": 1200,
    "duration": 9200,
    "waiting_time": 200,
    "distance": 33800,
    "violations": []
  },
  "routes": [
    {
      "vehicle": 1,
      "steps": [
        {"type": "start", "location": [126.9780, 37.5665]},
        {"type": "job", "id": 101, "location": [127.0276, 37.4979]},
        {"type": "job", "id": 103, "location": [126.9910, 37.5512]},
        {"type": "end", "location": [126.9780, 37.5665]}
      ]
    },
    {
      "vehicle": 2,
      "steps": [
        {"type": "start", "location": [127.0594, 37.5140]},
        {"type": "job", "id": 102, "location": [127.0594, 37.5140]},
        {"type": "end", "location": [127.0594, 37.5140]}
      ]
    }
  ],
  "unassigned": [],
  "analysis": {
    "quality_score": 0.95,
    "suggestions": [],
    "vehicle_utilization": [
      {"vehicle_id": 1, "utilization": 0.88, "tasks": 2},
      {"vehicle_id": 2, "utilization": 0.70, "tasks": 1}
    ]
  },
  "statistics": {
    "distances": {"total": 33800, "per_vehicle": [17500, 16300]},
    "durations": {"total": 9200, "per_vehicle": [4600, 4600]},
    "averages": {"distance_per_task": 11267, "duration_per_task": 3067}
  },
  "multi_scenario_metadata": {
    "scenarios_evaluated": 3,
    "best_scenario": "scenario_2",
    "two_pass_enabled": true,
    "improvement_over_baseline": 0.08
  },
  "_metadata": {
    "version": "3.0",
    "mode": "optimize/premium",
    "pipeline": ["preprocessing", "unreachable_filter", "multi_scenario", "two_pass", "vroom", "analysis", "statistics"],
    "cache_hit": false,
    "processing_time_ms": 3800
  }
}
```

**상태 코드**:

| 코드 | 설명 |
|------|------|
| `200 OK` | 최적화 성공 |
| `400 Bad Request` | 잘못된 입력 |
| `401 Unauthorized` | API Key 누락 또는 유효하지 않음 |
| `403 Forbidden` | API Key에 프리미엄 권한 없음 |
| `429 Too Many Requests` | 요청률 제한 초과 |
| `500 Internal Server Error` | 내부 오류 |

---

### 7. POST /matrix/build -- 청크 매트릭스

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

**상태 코드**:

| 코드 | 설명 |
|------|------|
| `200 OK` | 매트릭스 생성 성공 |
| `400 Bad Request` | 잘못된 입력 (좌표 형식 오류 등) |
| `401 Unauthorized` | API Key 누락 또는 유효하지 않음 |
| `429 Too Many Requests` | 요청률 제한 초과 |
| `500 Internal Server Error` | OSRM 연결 오류 또는 내부 오류 |

---

### 8. POST /map-matching/match -- GPS 궤적 매칭

GPS 궤적을 도로 네트워크에 매칭한다. 선택적 GPS 보정 방식을 사용하여, 정확도가 낮은 구간(20m 초과)만 OSRM Route API로 보정하고, 정확도가 높은 원본 포인트는 그대로 보존한다.

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

각 포인트는 반드시 5개의 값을 포함해야 하며, 시간순으로 정렬되어야 한다.

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
    ],
    "enable_debug": false
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
      [126.9820, 37.5644, 1700000025, 2.0],
      [126.9832, 37.5639, 1700000030, 0.5],
      [126.9850, 37.5630, 1700000040, 1.0],
      [126.9870, 37.5620, 1700000050, 1.0]
    ],
    "summary": {
      "total_points": 6,
      "matched_points": 7
    },
    "debug_info": null
  }
}
```

**matched_trace 포인트 형식**: `[lon, lat, timestamp, flag]`

**flag 값 설명**:

| flag | 설명 |
|:----:|------|
| `0.5` | 보정된 포인트 (도로에 스냅됨) |
| `1.0` | 원본 포인트 (변경 없이 유지) |
| `2.0` | 생성된 포인트 (도로를 따라 추가된 중간 포인트) |
| `2.5` | 보간된 포인트 |
| `4.0` | 도로 점프 감지됨 |

**상태 코드**:

| 코드 | 설명 |
|------|------|
| `200 OK` | 매칭 성공 |
| `400 Bad Request` | 잘못된 입력 (포인트 수 부족, 형식 오류 등) |
| `401 Unauthorized` | API Key 누락 또는 유효하지 않음 |
| `429 Too Many Requests` | 요청률 제한 초과 |
| `500 Internal Server Error` | OSRM 연결 오류 또는 내부 오류 |

---

### 9. GET /map-matching/health -- 맵 매칭 헬스

맵 매칭 서비스의 상태를 확인한다. OSRM 서버와의 연결을 서울시청에서 을지로까지의 샘플 경로로 테스트한다.

**인증**: 불필요

**요청**:

```bash
curl http://localhost:8000/map-matching/health
```

**응답 예시**:

```json
{
  "status": "ok",
  "message": "Map matching service is healthy",
  "osrm_url": "http://osrm:5000",
  "osrm_status": "ok",
  "timestamp": "2025-02-15T09:30:00.123456"
}
```

**상태 코드**:

| 코드 | 설명 |
|------|------|
| `200 OK` | 맵 매칭 서비스 정상 |
| `503 Service Unavailable` | OSRM 서버 연결 불가 |

---

### 10. POST /map-matching/validate -- 궤적 검증

GPS 궤적의 품질을 검증한다. 실제 맵 매칭을 수행하지 않고 입력 데이터의 유효성과 품질 지표만 반환한다.

**인증**: 필요 (`X-API-Key` 헤더)

**요청 형식**: `/map-matching/match`와 동일

**요청**:

```bash
curl -X POST http://localhost:8000/map-matching/validate \
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
  "is_valid": true,
  "total_points": 6,
  "quality_score": 0.85,
  "issues": [
    {
      "type": "low_accuracy",
      "point_index": 2,
      "message": "GPS 정확도가 낮습니다 (25.0m)"
    },
    {
      "type": "low_accuracy",
      "point_index": 3,
      "message": "GPS 정확도가 낮습니다 (30.0m)"
    }
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

**상태 코드**:

| 코드 | 설명 |
|------|------|
| `200 OK` | 검증 완료 |
| `400 Bad Request` | 잘못된 입력 |
| `401 Unauthorized` | API Key 누락 또는 유효하지 않음 |
| `429 Too Many Requests` | 요청률 제한 초과 |
| `500 Internal Server Error` | 내부 오류 |

---

### 11. DELETE /cache/clear -- 캐시 초기화

캐시된 최적화 결과를 모두 삭제한다. Redis가 활성화된 경우 Redis 캐시를, 그렇지 않으면 인메모리 캐시를 초기화한다.

**인증**: 필요 (`X-API-Key` 헤더)

**요청**:

```bash
curl -X DELETE http://localhost:8000/cache/clear \
  -H "X-API-Key: demo-key-12345"
```

**응답 예시**:

```json
{
  "status": "ok",
  "message": "Cache cleared successfully",
  "cleared_entries": 42
}
```

**상태 코드**:

| 코드 | 설명 |
|------|------|
| `200 OK` | 캐시 초기화 성공 |
| `401 Unauthorized` | API Key 누락 또는 유효하지 않음 |
| `429 Too Many Requests` | 요청률 제한 초과 |
| `500 Internal Server Error` | 내부 오류 |

---

## 요청 형식

### 기본 구조

```json
{
  "vehicles": [...],        // 필수
  "jobs": [...],            // jobs 또는 shipments 중 하나 필수
  "shipments": [...],       // 선택
  "options": {...},         // 선택 (VROOM 옵션)
  "use_cache": true,        // 선택 (/optimize 전용)
  "business_rules": {...}   // 선택 (/optimize, /optimize/premium 전용)
}
```

### Vehicles (차량)

```json
{
  "vehicles": [
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
        {
          "id": 1,
          "time_windows": [[43200, 46800]],
          "service": 3600
        }
      ]
    }
  ]
}
```

| 필드 | 타입 | 필수 | 설명 | 예시 |
|------|------|:----:|------|------|
| `id` | integer | 필수 | 차량 고유 ID | `1` |
| `start` | [lon, lat] | 필수 | 시작 위치 (경도, 위도) | `[126.9780, 37.5665]` |
| `end` | [lon, lat] | 선택 | 종료 위치 (없으면 start와 동일) | `[126.9780, 37.5665]` |
| `capacity` | [int, ...] | 선택 | 용량 (다차원 가능) | `[100]` 또는 `[100, 50]` |
| `skills` | [int, ...] | 선택 | 보유 기술 목록 | `[1, 2, 3]` |
| `time_window` | [start, end] | 선택 | 근무 시간 (초 단위) | `[28800, 64800]` |
| `max_tasks` | integer | 선택 | 최대 배정 작업 수 | `10` |
| `speed_factor` | float | 선택 | 속도 계수 (기본 1.0) | `1.2` |
| `breaks` | array | 선택 | 휴식 시간 설정 | 아래 참조 |

**시간 변환 참고**:

```
08:00 = 8 * 3600 = 28800초
12:00 = 12 * 3600 = 43200초
13:00 = 13 * 3600 = 46800초
18:00 = 18 * 3600 = 64800초
```

### Jobs (작업)

```json
{
  "jobs": [
    {
      "id": 101,
      "location": [127.0276, 37.4979],
      "service": 300,
      "delivery": [10, 5],
      "pickup": [5, 2],
      "skills": [1, 3],
      "priority": 100,
      "time_windows": [
        [32400, 36000],
        [43200, 46800]
      ]
    }
  ]
}
```

| 필드 | 타입 | 필수 | 설명 | 예시 |
|------|------|:----:|------|------|
| `id` | integer | 필수 | 작업 고유 ID | `101` |
| `location` | [lon, lat] | 필수 | 작업 위치 | `[127.0276, 37.4979]` |
| `service` | integer | 선택 | 작업 소요 시간 (초) | `300` (5분) |
| `delivery` | [int, ...] | 선택 | 배송량 (capacity와 차원 일치) | `[10]` 또는 `[10, 5]` |
| `pickup` | [int, ...] | 선택 | 픽업량 | `[5]` |
| `skills` | [int, ...] | 선택 | 필요 기술 (모두 필요) | `[1, 3]` |
| `priority` | integer | 선택 | 우선순위 (0-100, 높을수록 우선) | `100` |
| `time_windows` | array | 선택 | 가능 시간대 (여러 개 가능) | `[[32400, 36000]]` |

### Shipments (픽업-배송 쌍)

```json
{
  "shipments": [
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
  ]
}
```

---

## 응답 형식

### 공통 응답 구조

모든 최적화 엔드포인트(`/distribute`, `/optimize`, `/optimize/basic`, `/optimize/premium`)는 아래의 공통 구조를 반환한다.

```json
{
  "code": 0,
  "summary": {...},
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

### 미배정 사유 유형

Wrapper가 미배정 작업에 추가하는 `reasons` 배열의 유형은 다음과 같다.

| type | 설명 | 정확도 |
|------|------|:------:|
| `skills` | 필요한 기술을 보유한 차량이 없음 | 100% |
| `capacity` | 작업 물량이 모든 차량의 용량을 초과 | 100% |
| `time_window` | 작업 시간대가 모든 차량의 근무 시간과 불일치 | 95% |
| `max_tasks` | 모든 차량의 최대 작업 수 초과 | 90% |
| `vehicle_time_window` | 차량 근무 시간과 불일치 | 95% |
| `no_vehicles` | 사용 가능한 차량 없음 | 100% |
| `unreachable` | OSRM에서 도달 불가능 판정 (v3.0 신규) | 100% |
| `complex_constraint` | 복합 제약 (최적화 과정에서 배제) | 70% |

#### 미배정 사유 상세 예시

**Skills 사유**:

```json
{
  "type": "skills",
  "description": "No vehicle has required skills",
  "details": {
    "required_skills": [3, 5],
    "available_vehicle_skills": [[1, 2], [1, 4]]
  }
}
```

**Capacity 사유**:

```json
{
  "type": "capacity",
  "description": "Job load exceeds all vehicle capacities",
  "details": {
    "job_delivery": [500],
    "job_pickup": [0],
    "vehicle_capacities": [[100], [200], [300]]
  }
}
```

**Time Window 사유**:

```json
{
  "type": "time_window",
  "description": "Job time windows incompatible with all vehicle time windows",
  "details": {
    "job_time_windows": [[64800, 72000]],
    "vehicle_time_windows": [[28800, 43200], [36000, 50400]]
  }
}
```

**Unreachable 사유** (v3.0 신규):

```json
{
  "type": "unreachable",
  "description": "Job location is unreachable via road network",
  "details": {
    "job_location": [127.1234, 37.5678],
    "threshold_seconds": 43200
  }
}
```

### 분석 및 통계

`/optimize` 및 `/optimize/premium` 엔드포인트가 반환하는 추가 분석 정보이다.

**analysis 구조**:

| 필드 | 타입 | 설명 |
|------|------|------|
| `quality_score` | float | 최적화 품질 점수 (0.0 ~ 1.0) |
| `suggestions` | [string] | 개선 제안 목록 |
| `vehicle_utilization` | array | 차량별 활용률 |

**statistics 구조**:

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
{
  "detail": "에러 메시지"
}
```

### 상태 코드 종합

| 상태 코드 | 설명 | 원인 |
|-----------|------|------|
| `200 OK` | 요청 성공 | - |
| `400 Bad Request` | 잘못된 입력 | vehicles 없음, jobs/shipments 없음, 필수 필드 누락, 좌표 형식 오류, trajectory 포인트 부족 |
| `401 Unauthorized` | 인증 실패 | API Key 누락 또는 유효하지 않은 키 |
| `403 Forbidden` | 권한 부족 | API Key에 해당 기능 권한 없음 (프리미엄 등) |
| `429 Too Many Requests` | 요청률 초과 | API Key별 요청 제한 초과 |
| `500 Internal Server Error` | 내부 오류 | VROOM 바이너리 실행 오류, OSRM 연결 오류, Wrapper 내부 예외 |
| `503 Service Unavailable` | 서비스 이용 불가 | OSRM 또는 핵심 컴포넌트 장애 |

### 에러 응답 예시

**400 Bad Request**:

```json
{"detail": "No vehicles provided"}
```

```json
{"detail": "No jobs or shipments provided"}
```

```json
{"detail": "Trajectory must contain at least 2 points"}
```

```json
{"detail": "Each trajectory point must have exactly 5 values: [lon, lat, timestamp, accuracy, speed]"}
```

**401 Unauthorized**:

```json
{"detail": "API key is missing. Provide X-API-Key header."}
```

```json
{"detail": "Invalid API key"}
```

**403 Forbidden**:

```json
{"detail": "Premium feature not available for this API key"}
```

**429 Too Many Requests**:

```json
{"detail": "Rate limit exceeded. Try again later."}
```

**500 Internal Server Error**:

```json
{"detail": "VROOM binary execution failed"}
```

```json
{"detail": "VROOM service timeout (>300 seconds)"}
```

---

## 환경 변수

서비스 동작을 제어하는 환경 변수 목록이다.

### 서버 설정

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `HOST` | `0.0.0.0` | 서버 바인딩 호스트 |
| `PORT` | `8000` | 서버 바인딩 포트 |
| `LOG_LEVEL` | `INFO` | 로그 레벨 (DEBUG, INFO, WARNING, ERROR) |

### VROOM 바이너리 설정

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `USE_DIRECT_CALL` | `true` | VROOM 바이너리 직접 호출 (v3.0 기본값) |
| `VROOM_BINARY_PATH` | `/usr/local/bin/vroom` | VROOM 바이너리 경로 |
| `VROOM_ROUTER` | `osrm` | 라우팅 엔진 |
| `VROOM_THREADS` | `4` | VROOM 실행 스레드 수 |
| `VROOM_EXPLORATION` | `5` | VROOM 탐색 강도 (높을수록 정밀, 느림) |
| `VROOM_TIMEOUT` | `300` | VROOM 실행 타임아웃 (초) |

### OSRM 설정

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `OSRM_URL` | `http://osrm:5000` | OSRM 서버 URL |
| `OSRM_CHUNK_SIZE` | `75` | 매트릭스 청크 크기 (75x75) |
| `OSRM_MAX_WORKERS` | `8` | 매트릭스 병렬 처리 워커 수 |

### 최적화 파이프라인 설정

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `TWO_PASS_ENABLED` | `false` | 2-Pass 최적화 활성화 |
| `TWO_PASS_MAX_WORKERS` | `4` | 2-Pass 병렬 워커 수 |
| `UNREACHABLE_FILTER_ENABLED` | `true` | 도달 불가 작업 사전 필터링 |
| `UNREACHABLE_THRESHOLD` | `43200` | 도달 불가 판정 기준 (초, 기본 12시간) |

### 캐시 설정

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `REDIS_URL` | `redis://redis:6379` | Redis 접속 URL (미연결 시 인메모리 폴백) |

### 맵 매칭 설정

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `MAP_MATCHING_ENABLED` | `true` | 맵 매칭 모듈 활성화 |

### 요청률 제한 설정

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `RATE_LIMIT_ENABLED` | `true` | 요청률 제한 활성화 |
| `RATE_LIMIT_REQUESTS` | `100` | 기간 내 최대 요청 수 |
| `RATE_LIMIT_WINDOW` | `3600` | 요청률 제한 기간 (초) |

---

## Docker 배포

### 서비스 구성

3개의 서비스로 구성된다: OSRM (라우팅 엔진), Redis (캐시), Wrapper (API 서버).

| 서비스 | 포트 | 설명 |
|--------|------|------|
| OSRM | `:5000` | 도로 기반 라우팅 엔진 |
| Redis | `:6379` | 캐시 저장소 |
| Wrapper | `:8000` | VROOM Wrapper API 서버 |

### 실행

```bash
docker compose -f docker-compose.v3.yml up -d
```

### 중지

```bash
docker compose -f docker-compose.v3.yml down
```

### 상태 확인

```bash
# 서비스 상태 확인
docker compose -f docker-compose.v3.yml ps

# Wrapper 헬스 체크
curl http://localhost:8000/health

# 맵 매칭 헬스 체크
curl http://localhost:8000/map-matching/health
```

---

## 버전 이력

### v3.0 (2025-02)

- VROOM 바이너리 직접 호출 (vroom-express 제거)
- 2-Pass 최적화 지원
- 도달 불가 작업 사전 필터링 (`unreachable` 사유 추가)
- OSRM 청크 매트릭스 빌더 (`/matrix/build` 엔드포인트)
- GPS 맵 매칭 모듈 (`/map-matching/match`, `/map-matching/validate`, `/map-matching/health`)

### v2.0 (2024)

- API Key 인증 체계
- 요청률 제한 (Rate Limiting)
- Redis 캐싱 지원
- 비즈니스 규칙 (VIP, 긴급 작업)
- 다단계 최적화 (`/optimize`, `/optimize/basic`, `/optimize/premium`)
- 제약 완화 자동 재시도
- 멀티 시나리오 최적화
- 품질 점수 및 통계 분석

### v1.0 (2024-01)

- 초기 릴리스
- 기본 최적화 기능
- 미배정 사유 분석 (skills, capacity, time_window 감지)

---

## 문의 및 지원

- **VROOM 공식 문서**: https://github.com/VROOM-Project/vroom/wiki
- **OSRM 공식 문서**: https://project-osrm.org/docs/v5.24.0/api/
- **v1.0 문서**: [archive/API-DOCUMENTATION.md](archive/API-DOCUMENTATION.md)
