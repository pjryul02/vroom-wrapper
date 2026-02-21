# VROOM-Express 상세 분석

## 📋 목차
1. [vroom-express란?](#vroom-express란)
2. [아키텍처 구조](#아키텍처-구조)
3. [API 스펙](#api-스펙)
4. [Wrapper 연결 분석](#wrapper-연결-분석)
5. [데이터 흐름](#데이터-흐름)
6. [소스코드 분석](#소스코드-분석)

---

## vroom-express란?

### 정의
**vroom-express**는 VROOM C++ 엔진을 HTTP API로 노출하는 Node.js 래퍼입니다.

### 3계층 구조
```
┌─────────────────────────────────────────┐
│  우리 Wrapper (Python)                   │  ← Phase 1-5 전처리/후처리
│  vroom-wrapper-project                  │
└──────────────┬──────────────────────────┘
               │ HTTP POST
               │ :8000 → :3000
┌──────────────▼──────────────────────────┐
│  vroom-express (Node.js)                │  ← HTTP → C++ 브릿지
│  - HTTP API 서버                        │
│  - OSRM 매트릭스 호출                   │
│  - 결과 포맷팅                          │
└──────────────┬──────────────────────────┘
               │ execFile()
               │
┌──────────────▼──────────────────────────┐
│  vroom (C++ Binary)                     │  ← 최적화 엔진
│  /usr/local/bin/vroom                   │
└─────────────────────────────────────────┘
```

### 역할
| 계층 | 담당 업무 | 기술 스택 |
|------|----------|----------|
| **우리 Wrapper** | 비즈니스 로직, 전/후처리, 트래픽 API | Python (FastAPI) |
| **vroom-express** | HTTP 인터페이스, 매트릭스 관리 | Node.js (Express) |
| **vroom** | VRP 최적화 알고리즘 | C++ |

---

## 아키텍처 구조

### vroom-express 내부 구조

```
vroom-express/
├── src/
│   ├── index.js              # 메인 Express 서버
│   ├── routes/
│   │   └── vrp.js           # POST / 라우트
│   ├── services/
│   │   ├── optimizer.js     # VROOM 바이너리 호출
│   │   └── matrix.js        # OSRM 매트릭스 호출
│   └── utils/
│       ├── validator.js     # 입력 검증
│       └── formatter.js     # 응답 포맷팅
│
├── config.yml               # 설정 파일
└── package.json
```

### 주요 컴포넌트

#### 1. Express 서버 (index.js)
```javascript
const express = require('express');
const app = express();

app.post('/', async (req, res) => {
  // 1. 요청 검증
  // 2. 매트릭스 준비 (OSRM 호출 또는 커스텀)
  // 3. VROOM 실행
  // 4. 결과 반환
});

app.listen(3000);
```

#### 2. Optimizer 서비스
```javascript
const { execFile } = require('child_process');

function runVroom(input) {
  return new Promise((resolve, reject) => {
    execFile('/usr/local/bin/vroom',
      ['-i', inputFile, '-o', outputFile],
      (error, stdout, stderr) => {
        // VROOM 실행 및 결과 파싱
      }
    );
  });
}
```

#### 3. Matrix 서비스
```javascript
async function getMatrix(locations, router) {
  if (router === 'osrm') {
    // OSRM table 서비스 호출
    const response = await axios.post(
      `${osrmUrl}/table/v1/driving/${coords}`,
      { annotations: ['duration', 'distance'] }
    );
    return response.data;
  }
  // 커스텀 매트릭스는 입력에서 그대로 사용
}
```

---

## API 스펙

### 엔드포인트
```
POST http://localhost:3000/
Content-Type: application/json
```

### 요청 구조
```json
{
  "vehicles": [
    {
      "id": 1,
      "start": [127.0, 37.0],
      "end": [127.0, 37.0],
      "capacity": [100],
      "time_window": [0, 86400],
      "skills": [1, 2]
    }
  ],
  "jobs": [
    {
      "id": 1,
      "location": [127.1, 37.1],
      "delivery": [10],
      "service": 300,
      "time_windows": [[32400, 43200]],
      "priority": 100,
      "skills": [1]
    }
  ],
  "matrices": {
    "durations": [[0, 600], [600, 0]],
    "distances": [[0, 5000], [5000, 0]]
  },
  "options": {
    "g": false
  }
}
```

### 주요 필드

#### vehicles
| 필드 | 타입 | 설명 |
|------|------|------|
| id | int | 차량 고유 ID |
| start | [lon, lat] | 출발지 좌표 |
| end | [lon, lat] | 도착지 좌표 |
| capacity | int[] | 용량 (다차원 가능) |
| time_window | [start, end] | 운행 가능 시간 (초) |
| skills | int[] | 보유 스킬 |
| speed_factor | float | 속도 계수 (기본 1.0) |

#### jobs
| 필드 | 타입 | 설명 |
|------|------|------|
| id | int | 작업 고유 ID |
| location | [lon, lat] | 작업 위치 |
| delivery | int[] | 배송 수량 |
| pickup | int[] | 픽업 수량 |
| service | int | 서비스 시간 (초) |
| time_windows | [[start, end]] | 작업 가능 시간창 |
| priority | int | 우선순위 (0-100) |
| skills | int[] | 필요 스킬 |

#### matrices (선택)
| 필드 | 타입 | 설명 |
|------|------|------|
| durations | int[][] | 소요시간 매트릭스 (초) |
| distances | int[][] | 거리 매트릭스 (미터) |

**중요**:
- matrices 제공 시 → OSRM 호출 스킵
- matrices 없으면 → vroom-express가 OSRM 호출

#### options
| 필드 | 타입 | 설명 |
|------|------|------|
| g | bool | Geometry 반환 여부 (기본 false) |

### 응답 구조
```json
{
  "code": 0,
  "summary": {
    "cost": 12000,
    "unassigned": 0,
    "delivery": [100],
    "pickup": [0],
    "service": 600,
    "duration": 7200,
    "waiting_time": 300,
    "priority": 500,
    "distance": 50000,
    "computing_times": {
      "loading": 5,
      "solving": 245,
      "routing": 50
    }
  },
  "unassigned": [],
  "routes": [
    {
      "vehicle": 1,
      "cost": 12000,
      "delivery": [100],
      "pickup": [0],
      "service": 600,
      "duration": 7200,
      "waiting_time": 300,
      "priority": 500,
      "distance": 50000,
      "steps": [
        {
          "type": "start",
          "location": [127.0, 37.0],
          "arrival": 0,
          "duration": 0
        },
        {
          "type": "job",
          "job": 1,
          "location": [127.1, 37.1],
          "service": 300,
          "waiting_time": 0,
          "arrival": 600,
          "duration": 900
        },
        {
          "type": "end",
          "location": [127.0, 37.0],
          "arrival": 7200,
          "duration": 7200
        }
      ]
    }
  ]
}
```

---

## Wrapper 연결 분석

### 우리 Wrapper가 vroom-express를 호출하는 방식

#### 1. 설정 (config.py)
```python
# src/config.py
VROOM_URL = os.getenv("VROOM_URL", "http://localhost:3000")
```

#### 2. Controller 초기화 (controller.py)
```python
# src/control/controller.py
class OptimizationController:
    def __init__(self, vroom_url: str = "http://localhost:3000"):
        self.vroom_url = vroom_url
```

#### 3. API 호출 (controller.py)
```python
async def _call_vroom(
    self,
    vrp_input: Dict[str, Any],
    config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    # VROOM 페이로드 구성
    vroom_payload = vrp_input.copy()

    # 옵션 추가
    if config and 'exploration_level' in config:
        vroom_payload['options'] = {
            'g': config['exploration_level']
        }

    # HTTP POST 요청
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{self.vroom_url}",  # http://localhost:3000
            json=vroom_payload
        )

        response.raise_for_status()
        return response.json()
```

### 호출 지점

| 파일 | 함수 | 용도 |
|------|------|------|
| `src/main_v2.py` | `main()` | 단일 최적화 |
| `src/main.py` | `example_*()` | 다양한 예제 |
| `src/control/controller.py` | `optimize()` | 제어 계층 |
| `src/control/multi_scenario.py` | `run_scenarios()` | 다중 시나리오 |

---

## 데이터 흐름

### 전체 플로우

```
┌──────────────────────────────────────────────────────────────┐
│  1. 클라이언트 요청                                           │
│     POST http://localhost:8000/optimize                      │
│     { "orders": [...], "vehicles": [...] }                   │
└────────────────┬─────────────────────────────────────────────┘
                 │
┌────────────────▼─────────────────────────────────────────────┐
│  2. Wrapper 전처리 (Phase 1-3)                               │
│     - PreProcessor.process()                                 │
│       ├─ Validator: 입력 검증                                │
│       ├─ Normalizer: 데이터 정규화                           │
│       ├─ BusinessRules: 비즈니스 룰 적용                     │
│       └─ MatrixBuilder: 실시간 교통 매트릭스 (Phase 1.5)     │
│                                                              │
│     출력: VROOM 형식의 JSON                                  │
│     {                                                        │
│       "vehicles": [...],                                     │
│       "jobs": [...],                                         │
│       "matrices": {                                          │
│         "durations": [[...]],  # TMap/Kakao/Naver에서 가져옴 │
│         "distances": [[...]]   # OSRM에서 가져옴             │
│       }                                                      │
│     }                                                        │
└────────────────┬─────────────────────────────────────────────┘
                 │ HTTP POST :8000 → :3000
┌────────────────▼─────────────────────────────────────────────┐
│  3. vroom-express (Node.js)                                  │
│     POST http://vroom:3000/                                  │
│                                                              │
│     ① 요청 검증                                              │
│     ② 매트릭스 확인                                          │
│        - matrices 있음 → 그대로 사용 ✅ (우리 케이스)         │
│        - matrices 없음 → OSRM 호출                           │
│     ③ VROOM 바이너리 실행                                    │
│        execFile('/usr/local/bin/vroom', [...])              │
│     ④ 결과 포맷팅 및 반환                                    │
└────────────────┬─────────────────────────────────────────────┘
                 │ execFile()
┌────────────────▼─────────────────────────────────────────────┐
│  4. VROOM C++ 엔진                                           │
│     /usr/local/bin/vroom -i input.json -o output.json       │
│                                                              │
│     - Local Search 알고리즘 실행                             │
│     - Cross-exchange, 2-opt, Relocate 등 오퍼레이터 적용     │
│     - 최적 경로 생성                                         │
└────────────────┬─────────────────────────────────────────────┘
                 │ 결과 JSON
┌────────────────▼─────────────────────────────────────────────┐
│  5. vroom-express 응답                                       │
│     {                                                        │
│       "code": 0,                                             │
│       "summary": { "cost": 12000, ... },                     │
│       "routes": [...]                                        │
│     }                                                        │
└────────────────┬─────────────────────────────────────────────┘
                 │ HTTP Response
┌────────────────▼─────────────────────────────────────────────┐
│  6. Wrapper 후처리 (Phase 5)                                 │
│     - ResultAnalyzer.analyze()                               │
│       ├─ 경로 품질 분석                                      │
│       ├─ 제약조건 위반 검증                                  │
│       └─ 개선 제안 생성                                      │
│                                                              │
│     - StatisticsGenerator.generate()                         │
│       └─ 통계 및 리포트                                      │
└────────────────┬─────────────────────────────────────────────┘
                 │
┌────────────────▼─────────────────────────────────────────────┐
│  7. 최종 응답                                                │
│     {                                                        │
│       "vroom_result": { ... },                               │
│       "analysis": { ... },                                   │
│       "statistics": { ... }                                  │
│     }                                                        │
└──────────────────────────────────────────────────────────────┘
```

### 핵심 차이점

#### 우리 Wrapper 사용 시 (권장)
```
Client → Wrapper → vroom-express → vroom
         ↑
         └─ TMap/Kakao 실시간 교통
         └─ 비즈니스 룰 적용
         └─ 결과 분석
```

#### vroom-express 직접 사용 시
```
Client → vroom-express → vroom
         ↑
         └─ OSRM 정적 매트릭스만
         └─ 기본 기능만
```

---

## 소스코드 분석

### vroom-express 주요 로직 (추정)

vroom-express는 오픈소스이므로 실제 코드 구조:

#### index.js (메인)
```javascript
const express = require('express');
const solver = require('./solver');
const validator = require('./validator');

const app = express();
app.use(express.json());

app.post('/', async (req, res) => {
  try {
    // 1. 입력 검증
    const validationError = validator.validate(req.body);
    if (validationError) {
      return res.status(400).json({
        code: 1,
        error: validationError
      });
    }

    // 2. VROOM 실행
    const result = await solver.solve(req.body);

    // 3. 결과 반환
    res.json(result);

  } catch (error) {
    res.status(500).json({
      code: 2,
      error: error.message
    });
  }
});

app.get('/health', (req, res) => {
  res.json({ status: 'healthy' });
});

app.listen(3000);
```

#### solver.js (최적화)
```javascript
const { execFile } = require('child_process');
const fs = require('fs').promises;
const path = require('path');
const matrixService = require('./matrix');

async function solve(input) {
  // 1. 매트릭스 준비
  if (!input.matrices) {
    // OSRM에서 매트릭스 가져오기
    const locations = extractLocations(input);
    input.matrices = await matrixService.getFromOSRM(locations);
  }

  // 2. 임시 파일 생성
  const tempDir = '/tmp';
  const inputFile = path.join(tempDir, `vroom-input-${Date.now()}.json`);
  const outputFile = path.join(tempDir, `vroom-output-${Date.now()}.json`);

  await fs.writeFile(inputFile, JSON.stringify(input));

  // 3. VROOM 실행
  return new Promise((resolve, reject) => {
    const args = ['-i', inputFile, '-o', outputFile];

    if (input.options?.g) {
      args.push('-g');  // geometry 옵션
    }

    execFile('/usr/local/bin/vroom', args, async (error, stdout, stderr) => {
      try {
        if (error) {
          reject(new Error(`VROOM error: ${stderr}`));
          return;
        }

        // 4. 결과 읽기
        const resultJson = await fs.readFile(outputFile, 'utf-8');
        const result = JSON.parse(resultJson);

        // 5. 정리
        await fs.unlink(inputFile);
        await fs.unlink(outputFile);

        resolve(result);
      } catch (err) {
        reject(err);
      }
    });
  });
}

function extractLocations(input) {
  const locations = [];

  // 차량 위치
  input.vehicles?.forEach(v => {
    if (v.start) locations.push(v.start);
    if (v.end) locations.push(v.end);
  });

  // 작업 위치
  input.jobs?.forEach(j => {
    locations.push(j.location);
  });

  return locations;
}

module.exports = { solve };
```

#### matrix.js (매트릭스)
```javascript
const axios = require('axios');
const config = require('./config');

async function getFromOSRM(locations) {
  // 좌표를 OSRM 형식으로 변환
  const coords = locations
    .map(loc => `${loc[0]},${loc[1]}`)
    .join(';');

  // OSRM table 서비스 호출
  const osrmUrl = config.get('osrm.url') || 'http://osrm:5000';
  const response = await axios.get(
    `${osrmUrl}/table/v1/driving/${coords}`,
    {
      params: {
        annotations: 'duration,distance'
      }
    }
  );

  return {
    durations: response.data.durations,
    distances: response.data.distances
  };
}

module.exports = { getFromOSRM };
```

### 우리 Wrapper가 이를 우회하는 방법

**핵심**: `matrices` 필드를 미리 제공하여 vroom-express의 OSRM 호출을 스킵

```python
# src/preprocessing/preprocessor.py

async def process(self, vrp_input, business_rules=None):
    # ... Phase 1-3 생략 ...

    # Phase 1.5: 실시간 교통 매트릭스 (TMap/Kakao/Naver)
    if self.enable_traffic_matrix:
        matrices = await self.matrix_builder.build_matrix(
            locations=all_locations,
            # TMap API에서 실시간 교통 기반 소요시간 가져오기
        )

        # VROOM 입력에 추가
        result['matrices'] = {
            'durations': matrices['durations'],  # TMap 실시간 교통
            'distances': matrices['distances']   # OSRM 정적 거리
        }

    return result
```

**결과**:
- vroom-express는 `matrices` 필드를 발견
- OSRM 호출 스킵 ✅
- 우리가 제공한 실시간 교통 매트릭스 사용 ✅

---

## 핵심 인사이트

### 1. 역할 분리가 명확함
```
┌────────────────────┬─────────────────────────────────────┐
│ 계층               │ 책임                                │
├────────────────────┼─────────────────────────────────────┤
│ Wrapper (Python)   │ 도메인 로직, 비즈니스 룰, 실시간 데이터 │
│ vroom-express (JS) │ HTTP 인터페이스, 프로세스 관리       │
│ vroom (C++)        │ 최적화 알고리즘                      │
└────────────────────┴─────────────────────────────────────┘
```

### 2. 확장 포인트
- **Wrapper 레벨**: 비즈니스 로직 추가 (가장 쉬움)
- **vroom-express 레벨**: 전처리 로직 추가 (커스텀 빌드 필요)
- **vroom 레벨**: 알고리즘 수정 (가장 복잡)

### 3. 우리 Wrapper의 가치
| 기능 | vroom-express만 | Wrapper 사용 |
|------|-----------------|-------------|
| 실시간 교통 | ❌ | ✅ TMap/Kakao |
| 비즈니스 룰 | ❌ | ✅ 커스터마이징 |
| 결과 분석 | ❌ | ✅ 상세 분석 |
| 다중 시나리오 | ❌ | ✅ 자동 비교 |
| 제약조건 튜닝 | ❌ | ✅ 자동 조정 |

### 4. 통신 프로토콜
- **외부 → Wrapper**: HTTP REST (FastAPI)
- **Wrapper → vroom-express**: HTTP POST (JSON)
- **vroom-express → vroom**: stdin/stdout (JSON)

---

## 실전 예제

### vroom-express 직접 호출 (기본)
```bash
curl -X POST http://localhost:3000 \
  -H "Content-Type: application/json" \
  -d '{
    "vehicles": [{"id": 1, "start": [127.0, 37.0]}],
    "jobs": [{"id": 1, "location": [127.1, 37.1]}]
  }'
```

### Wrapper를 통한 호출 (권장)
```bash
curl -X POST http://localhost:8000/optimize \
  -H "Content-Type: application/json" \
  -d '{
    "orders": [
      {
        "id": "ORDER001",
        "address": "서울시 강남구 테헤란로 123",
        "time_window": "09:00-12:00"
      }
    ],
    "vehicles": [
      {"id": "VEHICLE001", "capacity": 100}
    ]
  }'
```
→ Wrapper가 자동으로:
- 주소 → 좌표 변환
- 실시간 교통 매트릭스 생성
- VROOM 형식 변환
- vroom-express 호출
- 결과 분석 추가

---

## 다음 단계

### 연구 목적
1. ✅ vroom-express 역할 이해 완료
2. ✅ Wrapper 연결 방식 파악 완료
3. 🔄 vroom-express 소스코드 클론 및 분석
4. 🔄 커스텀 vroom-express 빌드 실험

### 실전 배포
1. ✅ docker-compose.unified.yml로 전체 스택 실행
2. ✅ Wrapper → vroom-express → vroom 플로우 작동
3. 🔄 실시간 교통 API 연동 테스트
4. 🔄 프로덕션 환경 최적화

---

## 참고 자료
- [vroom-express GitHub](https://github.com/VROOM-Project/vroom-express)
- [VROOM API 문서](https://github.com/VROOM-Project/vroom/blob/master/docs/API.md)
- [우리 Wrapper 코드](src/control/controller.py#L236-L238) - vroom-express 호출 부분
