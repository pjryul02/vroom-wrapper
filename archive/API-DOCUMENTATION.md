# VROOM Wrapper API 문서

## 📋 목차

1. [기본 정보](#기본-정보)
2. [엔드포인트](#엔드포인트)
3. [요청 형식](#요청-형식)
4. [응답 형식](#응답-형식)
5. [예제](#예제)
6. [에러 처리](#에러-처리)

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

현재 버전은 인증 없음. 프로덕션에서는 API Key 추가 권장.

```bash
# API Key 사용 시 (향후)
curl -H "X-API-Key: your-secret-key" http://localhost:8000/optimize
```

---

## 엔드포인트

### 1. Health Check

서비스 상태 확인

**Endpoint**: `GET /health`

**Request**:
```bash
curl http://localhost:8000/health
```

**Response**:
```json
{
  "wrapper": "ok",
  "vroom": "ok",
  "vroom_url": "http://localhost:3000"
}
```

**Status Codes**:
- `200 OK`: 모든 서비스 정상
- `502 Bad Gateway`: VROOM 서비스 연결 불가

---

### 2. Optimize (메인 API)

배차 최적화 + 미배정 사유 분석

**Endpoint**: `POST /optimize`

**Request**:
```bash
curl -X POST http://localhost:8000/optimize \
  -H "Content-Type: application/json" \
  -d @request.json
```

**Response**:
```json
{
  "code": 0,
  "summary": {...},
  "routes": [...],
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
  "_wrapper_info": {
    "version": "1.0",
    "features": ["unassigned_reasons"],
    "vroom_url": "http://localhost:3000"
  }
}
```

**Status Codes**:
- `200 OK`: 성공
- `400 Bad Request`: 잘못된 입력
- `502 Bad Gateway`: VROOM 서비스 오류
- `500 Internal Server Error`: Wrapper 내부 오류

---

## 요청 형식

### 기본 구조

```json
{
  "vehicles": [...],    // 필수
  "jobs": [...],        // jobs 또는 shipments 중 하나 필수
  "shipments": [...]    // 선택
}
```

### Vehicles (차량)

```json
{
  "vehicles": [
    {
      "id": 1,                              // 필수: 고유 ID
      "start": [126.9780, 37.5665],        // 필수: 시작 위치 [경도, 위도]
      "end": [126.9780, 37.5665],          // 선택: 종료 위치
      "capacity": [100, 50],                // 선택: 용량 (다차원 가능)
      "skills": [1, 2, 3],                  // 선택: 보유 기술
      "time_window": [28800, 64800],        // 선택: 근무 시간 (초)
      "max_tasks": 10,                      // 선택: 최대 작업 수
      "speed_factor": 1.0,                  // 선택: 속도 계수 (기본 1.0)
      "breaks": [                           // 선택: 휴식 시간
        {
          "id": 1,
          "time_windows": [[43200, 46800]], // 12:00-13:00
          "service": 3600                   // 1시간
        }
      ]
    }
  ]
}
```

#### 필드 설명

| 필드 | 타입 | 필수 | 설명 | 예시 |
|------|------|------|------|------|
| `id` | integer | ✅ | 차량 고유 ID | `1` |
| `start` | [lon, lat] | ✅ | 시작 위치 (경도, 위도) | `[126.9780, 37.5665]` |
| `end` | [lon, lat] | ❌ | 종료 위치 (없으면 start와 동일) | `[126.9780, 37.5665]` |
| `capacity` | [int, ...] | ❌ | 용량 (다차원 가능) | `[100]` 또는 `[100, 50]` |
| `skills` | [int, ...] | ❌ | 보유 기술 목록 | `[1, 2, 3]` |
| `time_window` | [start, end] | ❌ | 근무 시간 (초 단위) | `[28800, 64800]` |
| `max_tasks` | integer | ❌ | 최대 배정 작업 수 | `10` |
| `speed_factor` | float | ❌ | 속도 계수 (기본 1.0) | `1.2` |
| `breaks` | array | ❌ | 휴식 시간 설정 | 아래 참조 |

**시간 변환 예시**:
```python
# 08:00 = 8 * 3600 = 28800초
# 18:00 = 18 * 3600 = 64800초
time_window = [28800, 64800]  # 08:00 ~ 18:00
```

### Jobs (작업)

```json
{
  "jobs": [
    {
      "id": 101,                            // 필수: 고유 ID
      "location": [127.0276, 37.4979],     // 필수: 위치 [경도, 위도]
      "service": 300,                       // 선택: 작업 시간 (초)
      "delivery": [10, 5],                  // 선택: 배송량 (다차원)
      "pickup": [5, 2],                     // 선택: 픽업량
      "skills": [1, 3],                     // 선택: 필요 기술
      "priority": 100,                      // 선택: 우선순위 (0-100)
      "time_windows": [                     // 선택: 가능 시간대
        [32400, 36000],                     // 09:00-10:00
        [43200, 46800]                      // 12:00-13:00
      ]
    }
  ]
}
```

#### 필드 설명

| 필드 | 타입 | 필수 | 설명 | 예시 |
|------|------|------|------|------|
| `id` | integer | ✅ | 작업 고유 ID | `101` |
| `location` | [lon, lat] | ✅ | 작업 위치 | `[127.0276, 37.4979]` |
| `service` | integer | ❌ | 작업 소요 시간 (초) | `300` (5분) |
| `delivery` | [int, ...] | ❌ | 배송량 (capacity와 차원 일치) | `[10]` 또는 `[10, 5]` |
| `pickup` | [int, ...] | ❌ | 픽업량 | `[5]` |
| `skills` | [int, ...] | ❌ | 필요 기술 (모두 필요) | `[1, 3]` |
| `priority` | integer | ❌ | 우선순위 (0-100, 높을수록 우선) | `100` |
| `time_windows` | array | ❌ | 가능 시간대 (여러 개 가능) | `[[32400, 36000]]` |

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

### 성공 응답 구조

```json
{
  "code": 0,                    // 0: 성공
  "summary": {                  // 전체 요약
    "cost": 1234,
    "routes": 2,
    "unassigned": 3,
    "service": 900,
    "duration": 5400,
    "waiting_time": 0,
    "distance": 15000,
    "violations": []
  },
  "routes": [                   // 차량별 경로
    {
      "vehicle": 1,
      "cost": 600,
      "service": 300,
      "duration": 1200,
      "distance": 5000,
      "steps": [
        {
          "type": "start",
          "location": [126.9780, 37.5665],
          "arrival": 0,
          "duration": 0
        },
        {
          "type": "job",
          "id": 101,
          "location": [127.0276, 37.4979],
          "arrival": 600,
          "duration": 900,
          "service": 300,
          "load": [10]
        },
        {
          "type": "end",
          "location": [126.9780, 37.5665],
          "arrival": 1200,
          "duration": 1200
        }
      ],
      "violations": []
    }
  ],
  "unassigned": [               // 미배정 작업
    {
      "id": 102,
      "location": [127.0594, 37.5140],
      "type": "job",
      "reasons": [               // ★ Wrapper가 추가하는 필드
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
  "_wrapper_info": {            // ★ Wrapper 메타데이터
    "version": "1.0",
    "features": ["unassigned_reasons"],
    "vroom_url": "http://localhost:3000"
  }
}
```

### Violation Types (미배정 이유)

| Type | 설명 | 정확도 |
|------|------|--------|
| `skills` | 필요한 기술이 없음 | 100% |
| `capacity` | 용량 초과 | 100% |
| `time_window` | 시간 윈도우 불일치 | 95% |
| `max_tasks` | 최대 작업 수 초과 | 90% |
| `vehicle_time_window` | 차량 근무 시간과 불일치 | 95% |
| `no_vehicles` | 사용 가능한 차량 없음 | 100% |
| `complex_constraint` | 복합 제약 (최적화 과정에서 배제) | 70% |

### Violation Details 예시

#### Skills Violation
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

#### Capacity Violation
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

#### Time Window Violation
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

---

## 예제

### 예제 1: 기본 배차

**요청**:
```json
{
  "vehicles": [
    {
      "id": 1,
      "start": [126.9780, 37.5665],
      "end": [126.9780, 37.5665]
    }
  ],
  "jobs": [
    {
      "id": 101,
      "location": [127.0276, 37.4979]
    },
    {
      "id": 102,
      "location": [127.0594, 37.5140]
    }
  ]
}
```

**cURL**:
```bash
curl -X POST http://localhost:8000/optimize \
  -H "Content-Type: application/json" \
  -d '{
    "vehicles": [
      {"id": 1, "start": [126.9780, 37.5665], "end": [126.9780, 37.5665]}
    ],
    "jobs": [
      {"id": 101, "location": [127.0276, 37.4979]},
      {"id": 102, "location": [127.0594, 37.5140]}
    ]
  }'
```

**응답**:
```json
{
  "code": 0,
  "summary": {
    "cost": 1199,
    "routes": 1,
    "unassigned": 0,
    "distance": 19900
  },
  "routes": [
    {
      "vehicle": 1,
      "steps": [
        {"type": "start", "location": [126.9780, 37.5665]},
        {"type": "job", "id": 101, "location": [127.0276, 37.4979]},
        {"type": "job", "id": 102, "location": [127.0594, 37.5140]},
        {"type": "end", "location": [126.9780, 37.5665]}
      ]
    }
  ],
  "unassigned": []
}
```

### 예제 2: Skills 제약

**요청**:
```json
{
  "vehicles": [
    {
      "id": 1,
      "start": [126.9780, 37.5665],
      "skills": [1, 2]
    }
  ],
  "jobs": [
    {
      "id": 101,
      "location": [127.0276, 37.4979],
      "skills": [1]
    },
    {
      "id": 102,
      "location": [127.0594, 37.5140],
      "skills": [3]
    }
  ]
}
```

**응답**:
```json
{
  "routes": [
    {
      "vehicle": 1,
      "steps": [
        {"type": "start"},
        {"type": "job", "id": 101},
        {"type": "end"}
      ]
    }
  ],
  "unassigned": [
    {
      "id": 102,
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
  ]
}
```

### 예제 3: Capacity 제약

**요청**:
```json
{
  "vehicles": [
    {
      "id": 1,
      "start": [126.9780, 37.5665],
      "capacity": [100]
    }
  ],
  "jobs": [
    {
      "id": 101,
      "location": [127.0276, 37.4979],
      "delivery": [50]
    },
    {
      "id": 102,
      "location": [127.0594, 37.5140],
      "delivery": [200]
    }
  ]
}
```

**응답**:
```json
{
  "routes": [
    {
      "vehicle": 1,
      "steps": [
        {"type": "start"},
        {"type": "job", "id": 101, "load": [50]},
        {"type": "end"}
      ]
    }
  ],
  "unassigned": [
    {
      "id": 102,
      "reasons": [
        {
          "type": "capacity",
          "description": "Job load exceeds all vehicle capacities",
          "details": {
            "job_delivery": [200],
            "job_pickup": [0],
            "vehicle_capacities": [[100]]
          }
        }
      ]
    }
  ]
}
```

### 예제 4: Time Window 제약

**요청**:
```json
{
  "vehicles": [
    {
      "id": 1,
      "start": [126.9780, 37.5665],
      "time_window": [28800, 36000]
    }
  ],
  "jobs": [
    {
      "id": 101,
      "location": [127.0276, 37.4979],
      "time_windows": [[32400, 34200]]
    },
    {
      "id": 102,
      "location": [127.0594, 37.5140],
      "time_windows": [[64800, 72000]]
    }
  ]
}
```

**응답**:
```json
{
  "unassigned": [
    {
      "id": 102,
      "reasons": [
        {
          "type": "time_window",
          "description": "Job time windows incompatible with all vehicle time windows",
          "details": {
            "job_time_windows": [[64800, 72000]],
            "vehicle_time_windows": [[28800, 36000]]
          }
        }
      ]
    }
  ]
}
```

### 예제 5: 복합 시나리오 (실전)

**요청**:
```json
{
  "vehicles": [
    {
      "id": 1,
      "start": [126.9780, 37.5665],
      "end": [126.9780, 37.5665],
      "capacity": [100, 50],
      "skills": [1, 2],
      "time_window": [28800, 64800],
      "max_tasks": 5,
      "breaks": [
        {
          "id": 1,
          "time_windows": [[43200, 46800]],
          "service": 3600
        }
      ]
    },
    {
      "id": 2,
      "start": [127.0594, 37.5140],
      "end": [127.0594, 37.5140],
      "capacity": [200, 100],
      "skills": [2, 3],
      "time_window": [36000, 72000],
      "max_tasks": 8
    }
  ],
  "jobs": [
    {
      "id": 101,
      "location": [127.0276, 37.4979],
      "service": 300,
      "delivery": [20, 10],
      "skills": [1],
      "priority": 100,
      "time_windows": [[32400, 36000]]
    },
    {
      "id": 102,
      "location": [127.0594, 37.5140],
      "service": 600,
      "delivery": [30, 15],
      "skills": [3],
      "priority": 80,
      "time_windows": [[43200, 50400]]
    },
    {
      "id": 103,
      "location": [126.9910, 37.5512],
      "service": 300,
      "delivery": [500, 200],
      "skills": [1],
      "time_windows": [[50400, 54000]]
    }
  ]
}
```

---

## 에러 처리

### 에러 응답 형식

```json
{
  "detail": "Error message here"
}
```

### 에러 코드

| Status Code | 설명 | 원인 |
|-------------|------|------|
| `400 Bad Request` | 잘못된 입력 | - vehicles 없음<br>- jobs/shipments 없음<br>- 필수 필드 누락 |
| `502 Bad Gateway` | VROOM 서비스 오류 | - VROOM 연결 불가<br>- VROOM 타임아웃<br>- VROOM 에러 |
| `500 Internal Server Error` | Wrapper 내부 오류 | - 분석 로직 에러<br>- 예상치 못한 예외 |

### 에러 예시

#### 400 Bad Request
```json
{
  "detail": "No vehicles provided"
}
```

```json
{
  "detail": "No jobs provided"
}
```

#### 502 Bad Gateway
```json
{
  "detail": "VROOM service timeout (>5 minutes)"
}
```

```json
{
  "detail": "VROOM service unavailable"
}
```

---

## 클라이언트 라이브러리

### Python

```python
import requests

class VROOMClient:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url

    def health_check(self):
        """서비스 상태 확인"""
        response = requests.get(f"{self.base_url}/health")
        return response.json()

    def optimize(self, vehicles, jobs, shipments=None):
        """배차 최적화"""
        payload = {
            "vehicles": vehicles,
            "jobs": jobs
        }
        if shipments:
            payload["shipments"] = shipments

        response = requests.post(
            f"{self.base_url}/optimize",
            json=payload,
            timeout=300
        )
        response.raise_for_status()
        return response.json()

# 사용 예시
client = VROOMClient("http://YOUR_IP:8000")

result = client.optimize(
    vehicles=[{"id": 1, "start": [126.9780, 37.5665]}],
    jobs=[{"id": 101, "location": [127.0276, 37.4979]}]
)

print(f"배정: {result['summary']['routes']}개 경로")
print(f"미배정: {len(result['unassigned'])}개")
```

### JavaScript

```javascript
class VROOMClient {
  constructor(baseUrl = 'http://localhost:8000') {
    this.baseUrl = baseUrl;
  }

  async healthCheck() {
    const response = await fetch(`${this.baseUrl}/health`);
    return await response.json();
  }

  async optimize(vehicles, jobs, shipments = null) {
    const payload = { vehicles, jobs };
    if (shipments) payload.shipments = shipments;

    const response = await fetch(`${this.baseUrl}/optimize`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${await response.text()}`);
    }

    return await response.json();
  }
}

// 사용 예시
const client = new VROOMClient('http://YOUR_IP:8000');

const result = await client.optimize(
  [{id: 1, start: [126.9780, 37.5665]}],
  [{id: 101, location: [127.0276, 37.4979]}]
);

console.log(`배정: ${result.summary.routes}개 경로`);
console.log(`미배정: ${result.unassigned.length}개`);
```

---

## 제한사항

| 항목 | 기본값 | 설명 |
|------|--------|------|
| Max Vehicles | 200 | 최대 차량 수 |
| Max Jobs/Shipments | 1000 | 최대 작업 수 |
| Request Size | 1MB | 최대 요청 크기 |
| Timeout | 300초 | VROOM 실행 타임아웃 |

설정 변경: `vroom-conf/config.yml` 참조

---

## 성능

- **소규모** (10 vehicles, 50 jobs): ~1초
- **중규모** (50 vehicles, 200 jobs): ~5초
- **대규모** (200 vehicles, 1000 jobs): ~30초

Wrapper 오버헤드: 50-200ms (분석 시간)

---

## 버전 정보

**현재 버전**: 1.0

**변경 이력**:
- v1.0 (2024-01): 초기 릴리스
  - 기본 최적화 기능
  - 미배정 이유 분석
  - Skills, Capacity, Time Window 감지

---

## 문의 및 지원

- **GitHub Issues**: [레포지토리 URL]
- **문서**: [docs/VROOM-WRAPPER-COMPLETE-GUIDE.md](docs/VROOM-WRAPPER-COMPLETE-GUIDE.md)
- **VROOM 공식 문서**: https://github.com/VROOM-Project/vroom/wiki
